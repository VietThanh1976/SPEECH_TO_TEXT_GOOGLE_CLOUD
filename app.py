import streamlit as st
from streamlit_oauth import OAuth2
from google.cloud import speech
import os
import json
import tempfile
import pandas as pd

# --- Cấu Hình Trang và Tiêu Đề ---
st.set_page_config(
    page_title="Cloud STT App",
    page_icon="🗣️",
    layout="wide"
)

# --- 1. Thiết Lập Biến Bí Mật và OAuth ---
# Sử dụng st.secrets để truy cập các biến bí mật đã nhập trên Streamlit Cloud
try:
    CLIENT_ID = st.secrets["oauth_client_id"]
    CLIENT_SECRET = st.secrets["oauth_client_secret"]
    GCP_CREDENTIALS_JSON = st.secrets["gcp_credentials"]
    
    # URL chuyển hướng khi deploy trên Streamlit Cloud (PHẢI CẬP NHẬT)
    # Nếu chạy local: "http://localhost:8501"
    # Khi deploy: "https://[your-app-name].[region].streamlit.app/"
    REDIRECT_URI = "http://localhost:8501" # Cần thay đổi khi triển khai! 

    oauth = OAuth2(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        authorize_endpoint="https://accounts.google.com/o/oauth2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
        redirect_uri=REDIRECT_URI,
        scope=["https://www.googleapis.com/auth/userinfo.email"]
    )
except KeyError as e:
    st.error(f"Lỗi: Thiếu biến bí mật quan trọng trong Streamlit Secrets: {e}. Vui lòng kiểm tra lại file secrets.toml (local) hoặc cài đặt Secrets trên Streamlit Cloud.")
    st.stop()


# --- 2. Hàm Khởi Tạo Speech Client An Toàn ---
@st.cache_resource
def create_speech_client_from_secrets():
    """Tạo SpeechClient bằng cách sử dụng nội dung JSON key từ Streamlit secrets."""
    try:
        # Tải chuỗi JSON từ secrets
        credentials_dict = json.loads(GCP_CREDENTIALS_JSON)
        
        # Tạo file tạm thời (vì thư viện Google Cloud cần đường dẫn file)
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_key_file:
            json.dump(credentials_dict, temp_key_file)
            temp_key_file_path = temp_key_file.name
        
        # Khởi tạo SpeechClient
        client = speech.SpeechClient.from_service_account_json(temp_key_file_path)
        
        # Xóa file tạm thời (có thể lỗi nếu chạy trên môi trường sandbox bị giới hạn, 
        # nhưng ta vẫn cố gắng xóa)
        try:
            os.remove(temp_key_file_path)
        except Exception:
            pass # Bỏ qua lỗi nếu không thể xóa file tạm
            
        return client

    except Exception as e:
        st.error(f"Lỗi khi khởi tạo Google Cloud Speech Client: {e}")
        return None

# Khởi tạo client 
speech_client = create_speech_client_from_secrets()

# --- 3. Hàm Chuyển Đổi Âm Thanh thành Văn Bản ---
def transcribe_audio(uploaded_file, client):
    """Xử lý file âm thanh được tải lên và gọi Google Cloud Speech-to-Text."""
    if client is None:
        return "Lỗi: Speech Client chưa được khởi tạo thành công."

    temp_file_path = ""
    try:
        # Lưu file tạm thời để có thể đọc bằng google-cloud-speech
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Đọc nội dung file
        with io.open(temp_file_path, "rb") as audio_source:
            content = audio_source.read()
            audio = speech.RecognitionAudio(content=content)
        
        # Cấu hình cho ngôn ngữ (ví dụ: Tiếng Việt)
        config = speech.RecognitionConfig(
            # Encoding nên được xác định chính xác theo file nguồn (WAV thường là LINEAR16)
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000, # Rate thường là 16000 hoặc 8000
            language_code="vi-VN", 
        )

        with st.spinner("Đang gửi file và xử lý chuyển đổi..."):
            response = client.recognize(config=config, audio=audio)

        transcribed_text = ""
        for result in response.results:
            transcribed_text += result.alternatives[0].transcript + " "
        
        return transcribed_text.strip()

    except Exception as e:
        st.error(f"Lỗi xử lý API hoặc File: {e}")
        return f"Lỗi chuyển đổi: {e}"
    finally:
        # Đảm bảo xóa file tạm
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# --- 4. Hàm Giả Định Lấy Thông Tin Phí ---
def get_user_usage_info(user_email):
    """
    Hàm giả định theo dõi và hiển thị thông tin sử dụng và mức phí ước tính.
    Trong thực tế, việc truy cập Billing API rất phức tạp và cần backend.
    """
    total_free_minutes = 60 # Giới hạn miễn phí của GCP Speech-to-Text
    cost_per_minute = 0.024 # Ước tính $0.024/phút sau khi hết giới hạn
    
    # Dữ liệu giả định: Dùng Pandas hoặc CSDL để lưu trữ dữ liệu sử dụng thực tế
    # Ví dụ: Ta giả định một số dữ liệu đã được lưu trữ
    usage_records = {
        "user@gmail.com": 5.0,
        "test.user@gmail.com": 75.0, # Đã vượt giới hạn
    }
    
    minutes_used = usage_records.get(user_email, 0.0) # Mặc định 0 phút
    
    minutes_remaining = max(0, total_free_minutes - minutes_used)
    
    estimated_cost = 0.0
    status = "Vẫn trong giới hạn miễn phí"

    if minutes_used > total_free_minutes:
        chargeable_minutes = minutes_used - total_free_minutes
        estimated_cost = chargeable_minutes * cost_per_minute
        status = f"Đã vượt giới hạn. Phí ước tính: **${estimated_cost:.2f}**"
    
    return {
        "email": user_email,
        "used": f"{minutes_used:.1f} phút",
        "remaining": f"{minutes_remaining:.1f} phút",
        "status": status
    }

# --- 5. Giao Diện Chính Của Streamlit ---

st.title("🗣️ Ứng Dụng Chuyển Âm Thanh thành Văn Bản (STT) - GCP")
st.markdown("---")

# 5.1. Xử Lý Đăng Nhập
token = st.query_params.get("code")

if token is None and "user_email" not in st.session_state:
    # Chưa đăng nhập, hiển thị nút đăng nhập
    auth_url = oauth.get_authorization_url()
    st.info("Vui lòng Đăng nhập bằng Gmail để sử dụng ứng dụng.")
    st.markdown(f'<a href="{auth_url}" target="_self"><button style="background-color: #4285F4; color: white; padding: 10px 24px; border: none; border-radius: 4px; cursor: pointer;">Đăng Nhập bằng Gmail</button></a>', unsafe_allow_html=True)
    st.stop()
elif token and "user_email" not in st.session_state:
    # Đã nhận được code, đổi lấy token
    try:
        token = oauth.fetch_token(token)
        user_info = oauth.get_user_info(token)
        st.session_state["user_email"] = user_info['email']
        st.rerun() # Refresh để xóa tham số 'code' khỏi URL
        
    except Exception as e:
        st.error(f"Lỗi đăng nhập: {e}. Vui lòng kiểm tra lại cấu hình OAuth Client ID và Redirect URI.")
        st.stop()

# 5.2. Giao Diện Ứng Dụng Chính Sau Khi Đăng Nhập
if "user_email" in st.session_state:
    user_email = st.session_state["user_email"]
    
    # --- Sidebar Hiển Thị Thông Tin Sử Dụng ---
    st.sidebar.success(f"Chào mừng, {user_email}!")
    st.sidebar.header("📊 Thông Tin Sử Dụng & Phí")
    
    usage_data = get_user_usage_info(user_email)
    
    st.sidebar.metric(label="Phút Miễn Phí Đã Dùng", value=usage_data['used'], delta=f"Còn lại: {usage_data['remaining']}")
    st.sidebar.markdown(f"**Trạng thái Phí:** {usage_data['status']}")
    st.sidebar.markdown(f"*(Dựa trên giới hạn miễn phí 60 phút/tháng của Google Cloud)*")
    
    st.sidebar.markdown("---")
    
    if st.sidebar.button("Đăng Xuất"):
        # Xóa session state và refresh
        del st.session_state["user_email"]
        st.rerun()
    
    # --- Khu Vực Chuyển Đổi Âm Thanh ---
    st.header("Upload File Âm Thanh để Chuyển Đổi")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Chọn file âm thanh (.wav, .mp3, .flac). Khuyến nghị dùng WAV 16000Hz.",
            type=["wav", "mp3", "flac"]
        )

        if uploaded_file is not None:
            st.audio(uploaded_file, format='audio/wav' if uploaded_file.type == 'audio/wav' else uploaded_file.type)
            
            if st.button("Bắt Đầu Chuyển Đổi"):
                st.session_state['transcript'] = transcribe_audio(uploaded_file, speech_client)
    
    with col2:
        st.subheader("📝 Kết Quả Văn Bản")
        if 'transcript' in st.session_state:
            st.code(st.session_state['transcript'], language='text')
        else:
            st.info("Kết quả chuyển đổi sẽ hiển thị tại đây sau khi bạn nhấn nút.")