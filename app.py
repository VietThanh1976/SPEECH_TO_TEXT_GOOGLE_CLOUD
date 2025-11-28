import streamlit as st
import io
from google.cloud import speech
import os
import json
import tempfile
import pandas as pd

# --- 1. Cấu Hình Trang và Tiêu Đề ---
st.set_page_config(
    page_title="Ứng dụng Chuyển Âm thanh thành Văn bản",
    page_icon="🗣️",
    layout="wide"
)

# --- 2. Khởi Tạo Speech Client AN TOÀN ---
# Sử dụng @st.cache_resource để chỉ khởi tạo client một lần
@st.cache_resource
def create_speech_client_from_secrets():
    """Tạo SpeechClient bằng cách sử dụng nội dung JSON key từ Streamlit secrets."""
    
    # Khởi tạo biến file tạm an toàn
    temp_file_path = None
    GCP_CREDENTIALS_JSON = None 
    
    try:
        # Lấy JSON key của Google Cloud Service Account. Đây là bước kiểm tra lỗi KeyError ban đầu
        GCP_CREDENTIALS_JSON = st.secrets["gcp_credentials"]
    except KeyError:
        # Báo lỗi nếu thiếu biến gcp_credentials
        st.error("Lỗi: Thiếu 'gcp_credentials' trong Streamlit Secrets. Vui lòng kiểm tra lại PHẦN 2 cấu hình (KHÔNG CÓ DẤU [] cho gcp_credentials).")
        return None
        
    try:
        # 2. Xử lý chuỗi JSON và tạo file tạm
        
        # Thử tải và phân tích chuỗi JSON
        credentials_dict = json.loads(GCP_CREDENTIALS_JSON)
        
        # --- TẠM THỜI GỠ LỖI: KIỂM TRA ĐỘ CHÍNH XÁC CỦA BIẾN ---
        # Khối này giúp bạn biết liệu biến có được đọc và phân tích JSON đúng không.
        st.sidebar.subheader("⚠️ DEBUG: Trạng thái Key (Xóa sau khi hoạt động)")
        st.sidebar.write(f"Độ dài chuỗi JSON: **{len(GCP_CREDENTIALS_JSON)}** ký tự.")
        st.sidebar.write(f"Các khóa JSON tìm thấy: **{', '.join(credentials_dict.keys())}**")
        
        required_keys = ["type", "project_id", "private_key"]
        if not all(k in credentials_dict for k in required_keys):
            st.sidebar.error("Lỗi cấu trúc: Thiếu khóa bắt buộc (type, project_id, hoặc private_key). Vui lòng kiểm tra lại nội dung JSON.")
            return None
        # --- KẾT THÚC GỠ LỖI ---
        
        # Tạo file tạm thời vì Google Cloud Client Libraries yêu cầu đường dẫn file
        temp_dir = tempfile.gettempdir()
        
        # Ghi nội dung JSON vào file tạm
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_key_file:
            json.dump(credentials_dict, temp_key_file)
            temp_file_path = temp_key_file.name # Lấy đường dẫn file tạm
        
        # 3. Khởi tạo SpeechClient
        client = speech.SpeechClient.from_service_account_json(temp_file_path)
        
        st.sidebar.success("✅ Kết nối GCP Speech API thành công!")
        return client

    except json.JSONDecodeError as e:
        # Báo lỗi nếu việc phân tích JSON thất bại
        st.sidebar.error(f"❌ Lỗi Cú pháp JSON: Key GCP Key không hợp lệ. Vui lòng kiểm tra dấu phẩy hoặc ký tự thừa: {e}")
        return None
        
    except Exception as e:
        # Báo lỗi nếu khởi tạo client thất bại (Lỗi 'No key could be detected' sẽ nằm ở đây)
        st.sidebar.error(f"❌ Lỗi GCP Key: {e}")
        return None
        
    finally:
        # 4. Dọn dẹp an toàn (luôn chạy)
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as cleanup_e:
                print(f"Lỗi dọn dẹp file tạm: {cleanup_e}")


# Khởi tạo client 
speech_client = create_speech_client_from_secrets()

# --- 3. Hàm Chuyển Đổi Âm Thanh thành Văn Bản ---
def transcribe_audio(uploaded_file, client):
    """Xử lý file âm thanh được tải lên và gọi Google Cloud Speech-to-Text."""
    if client is None:
        st.error("Không thể chuyển đổi: Kết nối GCP API thất bại.")
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
        
        # Cấu hình cho ngôn ngữ (Mặc định Tiếng Việt)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, # Cần phù hợp với file
            sample_rate_hertz=16000, # Cần phù hợp với file
            language_code="vi-VN", 
        )

        with st.spinner("Đang gửi file và xử lý chuyển đổi..."):
            # Gọi API chuyển đổi
            response = client.recognize(config=config, audio=audio)

        transcribed_text = ""
        for result in response.results:
            transcribed_text += result.alternatives[0].transcript + " "
        
        return transcribed_text.strip()

    except Exception as e:
        st.error(f"Lỗi xử lý API hoặc File: Vui lòng kiểm tra định dạng/tần số âm thanh (ví dụ: cần WAV 16000Hz). Lỗi chi tiết: {e}")
        return f"Lỗi chuyển đổi: {e}"
    finally:
        # Đảm bảo xóa file tạm
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# --- 4. Hàm Giả Định Lấy Thông Tin Phí ---
def get_user_usage_info(user_email):
    """Hàm giả định hiển thị thông tin sử dụng và phí."""
    total_free_minutes = 60
    cost_per_minute = 0.024
    
    usage_records = {
        "admin@example.com": 5.0,
        "guest@example.com": 75.0,
    }
    
    minutes_used = usage_records.get(user_email, 0.0) 
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


# --- 5. Giao Diện Chính Của Streamlit và Xử Lý Native OAuth ---

st.title("🗣️ Ứng Dụng Chuyển Âm Thanh thành Văn Bản (STT) - GCP")
st.markdown("---")

# 5.1. Khởi tạo Native OAuth Connection
try:
    # Kết nối phải được đặt tên là "google_oauth" trong secrets.toml
    conn = st.connection("google_oauth", type="oauth")
except Exception:
    st.error("Lỗi: Không tìm thấy cấu hình OAuth 'google_oauth'. Vui lòng kiểm tra lại PHẦN 1 cấu hình trong Streamlit Secrets.")
    st.stop()
    

# Xử lý luồng đăng nhập
if "user_info" not in st.session_state:
    
    conn.authorize()
    
    try:
        # Lấy thông tin người dùng sau khi xác thực thành công
        user_info = conn.get_user_info()
        st.session_state["user_info"] = user_info
        st.session_state["user_email"] = user_info.get("email", "Email không xác định")
        st.rerun() 
        
    except Exception:
        # Nếu chưa đăng nhập hoặc có lỗi, hiển thị thông báo
        st.info("Vui lòng Đăng nhập bằng Gmail để sử dụng ứng dụng.")
        st.stop() 


# 5.2. Giao Diện Ứng Dụng Chính Sau Khi Đăng Nhập
user_email = st.session_state["user_email"]
    
# --- Sidebar Hiển Thị Thông Tin Sử Dụng ---
st.sidebar.success(f"Chào mừng, {user_email}!")
st.sidebar.header("📊 Thông Tin Sử Dụng (Giả định)")
    
usage_data = get_user_usage_info(user_email)
    
st.sidebar.metric(label="Phút Miễn Phí Đã Dùng", value=usage_data['used'], delta=f"Còn lại: {usage_data['remaining']}")
st.sidebar.markdown(f"**Trạng thái Phí:** {usage_data['status']}")
st.sidebar.markdown("---")
    
if st.sidebar.button("Đăng Xuất"):
    if "user_info" in st.session_state:
        del st.session_state["user_info"]
    if "user_email" in st.session_state:
        del st.session_state["user_email"]
    conn.log_out() 
    st.rerun()
    
# --- Khu Vực Chuyển Đổi Âm Thanh ---
st.header("Upload File Âm Thanh để Chuyển Đổi")
    
col1, col2 = st.columns([1, 2])
    
with col1:
    uploaded_file = st.file_uploader(
        "Chọn file âm thanh (.wav, .mp3, .flac).",
        type=["wav", "mp3", "flac"]
    )

    if uploaded_file is not None:
        st.audio(uploaded_file, format=uploaded_file.type)
            
        if st.button("Bắt Đầu Chuyển Đổi"):
            st.session_state['transcript'] = transcribe_audio(uploaded_file, speech_client)
    
with col2:
    st.subheader("📝 Kết Quả Văn Bản")
    if 'transcript' in st.session_state:
        st.code(st.session_state['transcript'], language='text')
    else:
        st.info("Kết quả chuyển đổi sẽ hiển thị tại đây sau khi bạn nhấn nút.")