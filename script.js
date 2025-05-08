document.addEventListener('DOMContentLoaded', () => {
    const countryInput = document.getElementById('countryInput');
    const searchButton = document.getElementById('searchButton');
    const chatArea = document.getElementById('chatArea'); // Đổi tên id
    const initialMessage = document.querySelector('.initial-message'); // Lấy tin nhắn ban đầu

    const backendUrl = 'http://127.0.0.1:5000/get_country_info';

    // Function để thêm một tin nhắn mới vào chat area
    function addMessage(sender, content, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', `${sender}-message`);

        let iconClass = '';
        if (sender === 'agent') {
            iconClass = isError ? 'fas fa-exclamation-circle' : 'fas fa-robot'; // Icon robot hoặc error
        } else { // sender === 'user'
            iconClass = 'fas fa-user'; // Icon user
        }

        messageDiv.innerHTML = `
            <i class="${iconClass} icon"></i>
            <div class="message-content">
                ${content}
            </div>
        `;
        chatArea.appendChild(messageDiv);
        // Cuộn xuống dưới cùng
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    // Function để thêm indicator đang gõ
    function addTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.classList.add('message', 'agent-message', 'typing-indicator');
        typingDiv.innerHTML = `
            <i class="fas fa-robot icon"></i>
            <div class="message-content">Đang xử lý...</div>
        `;
        chatArea.appendChild(typingDiv);
         // Cuộn xuống dưới cùng
        chatArea.scrollTop = chatArea.scrollHeight;
        return typingDiv; // Trả về element để có thể xóa sau
    }

    // Function để xóa indicator đang gõ
    function removeTypingIndicator(indicatorElement) {
        if (indicatorElement && indicatorElement.parentNode) {
            indicatorElement.parentNode.removeChild(indicatorElement);
        }
    }

    // Xóa tin nhắn ban đầu khi người dùng bắt đầu nhập
    countryInput.addEventListener('input', () => {
        if (initialMessage && initialMessage.parentNode) {
             initialMessage.parentNode.removeChild(initialMessage);
             // Loại bỏ listener sau khi đã xóa
             countryInput.removeEventListener('input', arguments.callee); // Lưu ý: arguments.callee có thể bị deprecated
             // Cách tốt hơn: Dùng một flag hoặc tên hàm riêng
        }
    });
     // Cách thay thế để xử lý việc xóa tin nhắn ban đầu chỉ một lần:
     let isInitialMessageRemoved = false;
     countryInput.addEventListener('input', () => {
         if (!isInitialMessageRemoved && initialMessage && initialMessage.parentNode) {
              initialMessage.parentNode.removeChild(initialMessage);
              isInitialMessageRemoved = true;
         }
     });


    async function performSearch() {
         const countryName = countryInput.value.trim();

        if (countryName === '') {
            addMessage('agent', 'Vui lòng nhập tên quốc gia.', true); // Thông báo lỗi từ agent
            return;
        }

        // Thêm tin nhắn của người dùng vào chat
        addMessage('user', countryName);

        // Xóa nội dung input sau khi gửi
        countryInput.value = '';


        // --- Feedback loading/typing ---
        const typingIndicator = addTypingIndicator(); // Thêm indicator
        searchButton.disabled = true;
        countryInput.disabled = true;
        // --- Kết thúc feedback loading/typing ---


        try {
            const response = await fetch(`${backendUrl}?country_name=${encodeURIComponent(countryName)}`);

            // --- Feedback loading/typing ---
            removeTypingIndicator(typingIndicator); // Xóa indicator
            searchButton.disabled = false;
            countryInput.disabled = false;
             countryInput.focus(); // Focus lại vào input sau khi search xong
            // --- Kết thúc feedback loading/typing ---


            if (!response.ok) {
                const errorData = await response.json();
                 addMessage('agent', `Lỗi: ${errorData.error || 'Không thể kết nối hoặc nhận dữ liệu từ server.'}`, true); // Hiển thị lỗi từ agent
                return;
            }

            const data = await response.json();

            if (data.error) {
                 addMessage('agent', `Lỗi: ${data.error}`, true); // Hiển thị lỗi từ backend
            } else {
                // Hiển thị thông tin quốc gia
                            const resultContent = `
                            <p class="country-info-item"><strong>Tên quốc gia:</strong> ${data.name}</p>
                            <p class="country-info-item"><strong>Thủ đô:</strong> ${data.capital}</p>
                            <p class="country-info-item"><strong>Dân số:</strong> ${data.population.toLocaleString()}</p>
                            <p class="country-info-item"><strong>Vùng:</strong> ${data.region}</p>
                            <p class="country-info-item"><strong>Tiểu vùng:</strong> ${data.subregion}</p>
                            <p class="country-info-item"><strong>Đơn vị tiền tệ:</strong> ${data.currency}</p>
                            <p class="country-info-item"><strong>Ngôn ngữ:</strong> ${data.language}</p>
                            `;
                            addMessage('agent', resultContent); // Thêm kết quả vào chat
            }

        } catch (error) {
            // --- Feedback loading/typing ---
            removeTypingIndicator(typingIndicator); // Xóa indicator
            searchButton.disabled = false;
            countryInput.disabled = false;
             countryInput.focus(); // Focus lại vào input sau khi search xong
            // --- Kết thúc feedback loading/typing ---

            addMessage('agent', `Đã xảy ra lỗi khi gọi API: ${error.message}`, true); // Hiển thị lỗi kết nối
        }
    }


    // Sự kiện nhấn nút Tra Cứu
    searchButton.addEventListener('click', performSearch);

    // Sự kiện nhấn Enter trong ô input
    countryInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault(); // Ngăn chặn hành vi mặc định
            performSearch(); // Gọi hàm tìm kiếm
        }
    });

});