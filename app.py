from google.cloud import speech
import io
import streamlit as st
from streamlit_oauth import OAuth2
import os
import json # Để xử lý GCP Credentials

# Đặt biến môi trường cho GCP Credentials, sử dụng nội dung từ secrets.toml
# Lưu ý: Trong Streamlit Cloud, bạn sẽ dùng st.secrets["gcp_credentials"]
# Để đơn giản, ta sẽ dùng trực tiếp st.secrets
# Tuy nhiên, cách an toàn hơn là tải credentials vào một biến
# và sử dụng nó để khởi tạo client.

def transcribe_audio(audio_file):
    """
    Chuyển đổi file âm thanh (local file path) thành văn bản.
    """
    try:
        # Khởi tạo client, sử dụng credentials từ file secrets.toml
        # Trong thực tế, bạn sẽ cần tải credentials JSON string 
        # và dùng nó để khởi tạo client
        
        # Cách giả định đơn giản hóa (cần được xử lý an toàn hơn):
        # client = speech.SpeechClient.from_service_account_json("path/to/your/key.json")
        # Hoặc dùng st.secrets.gcp_credentials để tải credentials
        
        # Do không thể biết format chính xác của st.secrets, ta sẽ giả định 
        # rằng đã cấu hình biến môi trường hoặc dùng method an toàn hơn.
        # Ở đây ta giả định đã cấu hình biến môi trường GOOGLE_APPLICATION_CREDENTIALS
        # cho môi trường local hoặc đã thiết lập Streamlit Cloud secrets đúng cách.
        client = speech.SpeechClient() 

        with io.open(audio_file, "rb") as audio_source:
            content = audio_source.read()
            audio = speech.RecognitionAudio(content=content)
        
        # Cấu hình cho ngôn ngữ (ví dụ: Tiếng Việt)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, # Hoặc FLAC/MP3 tùy file
            sample_rate_hertz=16000, # Phải khớp với file âm thanh
            language_code="vi-VN", # Hoặc "en-US",...
        )

        response = client.recognize(config=config, audio=audio)

        transcribed_text = ""
        for result in response.results:
            # Lấy bản ghi có độ tin cậy cao nhất
            transcribed_text += result.alternatives[0].transcript
        
        return transcribed_text

    except Exception as e:
        return f"Lỗi: {e}"



# --- Cấu Hình OAuth (Tải từ secrets.toml) ---
# Dùng st.secrets để truy cập các biến bí mật
client_id = st.secrets["oauth_client_id"]
client_secret = st.secrets["oauth_client_secret"]
redirect_uri = "http://localhost:8501" # Hoặc URI khi deploy (xem bước 5)

# Định nghĩa các thông số OAuth
oauth = OAuth2(
    client_id=client_id,
    client_secret=client_secret,
    authorize_endpoint="https://accounts.google.com/o/oauth2/auth",
    token_endpoint="https://oauth2.googleapis.com/token",
    redirect_uri=redirect_uri,
    scope=["https://www.googleapis.com/auth/userinfo.email"] # Chỉ cần email
)

# --- Hàm Giả Định Lấy Thông Tin Phí và Giới Hạn ---
# LƯU Ý QUAN TRỌNG: Truy cập thông tin phí GCP qua API thường là Billing API
# đòi hỏi quyền và cấu hình phức tạp. Trong một ứng dụng Streamlit đơn giản,
# cách thực tế nhất là tạo một "hệ thống giả định" hoặc "ước tính" 
# dựa trên việc theo dõi số lần gọi API và ước tính phí dựa trên giá công khai.

def get_user_usage_info(user_email):
    """
    Giả định: Lấy thông tin sử dụng và phí còn lại của người dùng.
    Thực tế: Cần kết nối với một CSDL/Hệ thống Backend để lưu trữ/tính toán
    số phút đã sử dụng của mỗi người dùng (dựa trên API Speech-to-Text).
    """
    # Giá công khai (ví dụ): $0.006/15 giây (hoặc $0.024/phút) cho Lvl 1
    # Giới hạn miễn phí: 60 phút/tháng
    
    # Dữ liệu giả định
    total_free_minutes = 60
    
    # Lấy dữ liệu sử dụng từ CSDL (thay thế bằng kết nối CSDL thực)
    if user_email == "test.user@gmail.com":
        minutes_used = 15.5
    else:
        minutes_used = 5.0 
        
    minutes_remaining = max(0, total_free_minutes - minutes_used)
    
    # Tính phí ước tính (ví dụ: chỉ tính phí sau 60 phút)
    if minutes_used > total_free_minutes:
        chargeable_minutes = minutes_used - total_free_minutes
        estimated_cost = chargeable_minutes * 0.024 # $0.024/phút
        status = f"Đã vượt giới hạn, phí ước tính: **${estimated_cost:.2f}**"
    else:
        status = "Vẫn trong giới hạn miễn phí"

    return {
        "email": user_email,
        "used": f"{minutes_used:.1f} phút",
        "remaining": f"{minutes_remaining:.1f} phút",
        "status": status
    }


# --- Giao Diện Chính Của Streamlit ---

st.title("🗣️ Ứng Dụng Chuyển Âm Thanh thành Văn Bản (STT)")

# 1. Xử Lý Đăng Nhập
token = st.query_params.get("code")

if token is None:
    # Chưa đăng nhập, hiển thị nút đăng nhập
    auth_url = oauth.get_authorization_url()
    st.markdown(f'<a href="{auth_url}" target="_self"><button style="background-color: #4CAF50; color: white; padding: 10px 24px; border: none; border-radius: 8px; cursor: pointer;">Đăng Nhập bằng Gmail</button></a>', unsafe_allow_html=True)
    st.stop()
else:
    # Đã nhận được code, đổi lấy token
    try:
        token = oauth.fetch_token(token)
        user_info = oauth.get_user_info(token)
        user_email = user_info['email']
        st.session_state["user_email"] = user_email
        st.sidebar.success(f"Chào mừng, {user_email}!")
        
    except Exception as e:
        st.error(f"Lỗi đăng nhập: {e}")
        st.stop()
        
    # --- Hiển Thị Thông Tin Sử Dụng ---
    st.sidebar.header("📊 Thông Tin Sử Dụng")
    usage_data = get_user_usage_info(st.session_state["user_email"])
    
    st.sidebar.markdown(f"* **Email:** `{usage_data['email']}`")
    st.sidebar.markdown(f"* **Đã dùng:** **{usage_data['used']}**")
    st.sidebar.markdown(f"* **Còn lại (Miễn phí):** **{usage_data['remaining']}**")
    st.sidebar.markdown(f"* **Trạng thái phí:** {usage_data['status']}")

    st.markdown("---")

    # 2. Xử Lý Chuyển Đổi Âm Thanh
    st.header("Upload File Âm Thanh")
    uploaded_file = st.file_uploader(
        "Chọn một file âm thanh (MP3, WAV, FLAC,...) *Lưu ý: Chỉ hỗ trợ file có định dạng phù hợp với API*",
        type=["mp3", "wav", "flac"]
    )

    if uploaded_file is not None:
        # Lưu file tạm thời để truyền cho Google Cloud Speech-to-Text (thư viện không hỗ trợ file Streamlit object trực tiếp)
        temp_file_path = os.path.join("/tmp", uploaded_file.name)
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.audio(uploaded_file, format='audio/wav')
        
        if st.button("Bắt Đầu Chuyển Đổi"):
            with st.spinner("Đang xử lý chuyển đổi..."):
                # Gọi hàm chuyển đổi
                transcript = transcribe_audio(temp_file_path)
                
                # Xóa file tạm
                os.remove(temp_file_path) 
            
            st.subheader("📝 Kết Quả Văn Bản")
            st.code(transcript, language='text')

