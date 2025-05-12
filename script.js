document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const voiceInputButton = document.getElementById('voice-input-button');
    const mapid = document.getElementById('mapid');

    // Updated: Only history content needed
    const historyContent = document.getElementById('history-content');
    // Removed tab buttons as favorites tab is gone
    // const tabButtons = document.querySelectorAll('.tab-button');

    const filterLanguageSelect = document.getElementById('filter-language'); // Keep filter for map


    const apiUrl = 'http://127.0.0.1:5000'; // Địa chỉ Backend Flask

    let mymap = null; // Variable to hold the map instance
    let currentMarker = null; // Variable to hold the current map marker

    // Simple in-memory history list for demonstration
    const searchHistory = [];
    const MAX_HISTORY_ITEMS = 10; // Limit history size

    // --- Chat functionality ---
    function addMessage(message, sender) {
        // *** START: Updated Scrolling Logic ***
        // Check if the user is near the bottom BEFORE adding the new message
        // This allows us to scroll down automatically only if they were already following the conversation
        const threshold = 50; // Pixels tolerance from the bottom
        const isAtOrNearBottom = chatBox.scrollHeight - chatBox.scrollTop <= chatBox.clientHeight + threshold;
        // *** END: Updated Scrolling Logic ***


        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);

        // Use innerHTML to allow basic HTML/markdown from AI (like tables)
        messageElement.innerHTML = message;

        chatBox.appendChild(messageElement);

        // *** START: Updated Scrolling Logic ***
        // Scroll to the bottom ONLY IF the user was already at or near the bottom
        if (isAtOrNearBottom) {
            chatBox.scrollTo({
                top: chatBox.scrollHeight,
                behavior: 'smooth'
            });
        }
        // If not near the bottom, do nothing. The user stays at their current scroll position.
        // *** END: Updated Scrolling Logic ***
    }

    function addToHistory(query) {
         // Add query to the top of the history list
         searchHistory.unshift({ query: query });
         // Limit history size
         if (searchHistory.length > MAX_HISTORY_ITEMS) {
             searchHistory.pop();
         }
         // Re-render history list
         renderHistory();
    }

    function renderHistory() {
        if (historyContent) {
            if (searchHistory.length > 0) {
                let html = '<ul>';
                searchHistory.forEach(item => {
                    // Make history items clickable to put query back in input
                    html += `<li data-query="${item.query.replace(/"/g, '"')}">${item.query}</li>`;
                });
                html += '</ul>';
                historyContent.innerHTML = html;

                // Add click listeners to history items
                historyContent.querySelectorAll('li').forEach(li => {
                    li.addEventListener('click', (event) => {
                        const query = event.target.dataset.query;
                        if (query) {
                            userInput.value = query;
                            userInput.focus(); // Focus input field
                        }
                    });
                });

            } else {
                historyContent.innerHTML = '<p>Lịch sử trống.</p>';
            }
        }
    }


    async function sendMessage() {
        const message = userInput.value.trim();
        if (message === '') return;

        addMessage(message, 'user');
        addToHistory(message); // Add user message to history

        userInput.value = ''; // Clear input

        // Disable input and button while waiting
        const elementsToDisable = [userInput, sendButton];
        if (voiceInputButton) elementsToDisable.push(voiceInputButton);
        elementsToDisable.forEach(el => el.disabled = true);

        try {
            // Call Backend API
            const response = await fetch(`${apiUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message }),
            });

            if (!response.ok) {
                // Attempt to read error response body
                 const errorBody = await response.text();
                 console.error('HTTP error details:', errorBody);
                 throw new Error(`HTTP error! status: ${response.status}`);
             }

            const data = await response.json();
            addMessage(data.reply, 'bot');

            // --- Handle Map Centering based on AI response ---
            if (data.country_latlng && mymap) {
                const latlng = data.country_latlng;
                // Use the common name provided by the backend for the popup title
                const countryName = data.country_name || 'Quốc gia';

                // Set view to country coordinates
                mymap.setView(latlng, 5); // Zoom level 5 is a good balance for country view

                // Add/update marker
                if (currentMarker) {
                    mymap.removeLayer(currentMarker);
                }
                // Updated popup text to Vietnamese
                currentMarker = L.marker(latlng).addTo(mymap)
                    .bindPopup(`<b>${countryName}</b><br>Vĩ độ: ${latlng[0].toFixed(2)}<br>Kinh độ: ${latlng[1].toFixed(2)}`)
                    .openPopup();
            } else {
                 // If no country data/latlng, maybe remove marker or reset view?
                 if (currentMarker) {
                     mymap.removeLayer(currentMarker);
                     currentMarker = null;
                 }
                 // Optional: reset map view to world or default location
                 // mymap.setView([20.0, 0.0], 2);
            }


        } catch (error) {
            console.error('Error sending message or processing response:', error);
            addMessage('Xin lỗi, đã có lỗi xảy ra khi kết nối với AI hoặc xử lý thông tin.', 'bot');
        } finally {
             // Re-enable input and button
             elementsToDisable.forEach(el => el.disabled = false);
             userInput.focus(); // Put focus back to input
        }
    }

    sendButton.addEventListener('click', sendMessage);

    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });

    // --- Voice Input (Web Speech API) ---
    // Check browser support
    if (voiceInputButton && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();

        recognition.continuous = false; // Stop after a single utterance
        recognition.lang = 'vi-VN'; // Set language to Vietnamese

        voiceInputButton.addEventListener('click', () => {
             try {
                recognition.start();
                voiceInputButton.textContent = '🔴 Nghe...'; // Indicate recording
                voiceInputButton.disabled = true;
                userInput.placeholder = 'Đang nghe...';
             } catch (e) {
                 console.error("SpeechRecognition start error:", e);
                 voiceInputButton.textContent = '🎤';
                 voiceInputButton.disabled = false;
                 userInput.placeholder = 'Nhập câu hỏi của bạn...';
             }
        });

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            userInput.value = transcript; // Put recognized text into input
            voiceInputButton.textContent = '🎤'; // Reset button text
            voiceInputButton.disabled = false;
            userInput.placeholder = 'Nhập câu hỏi của bạn...';
            // Optionally send message automatically: sendMessage();
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error', event.error);
            voiceInputButton.textContent = '🎤'; // Reset button text
            voiceInputButton.disabled = false;
            userInput.placeholder = 'Nhập câu hỏi của bạn...';
            // addMessage('Lỗi nhận dạng giọng nói: ' + event.error, 'bot'); // Too chatty?
        };

         recognition.onend = () => {
             voiceInputButton.textContent = '🎤'; // Reset button text if recording stops naturally
             voiceInputButton.disabled = false;
             userInput.placeholder = 'Nhập câu hỏi của bạn...';
         }

    } else {
        // Hide voice button if not supported
        if (voiceInputButton) {
            voiceInputButton.style.display = 'none';
        }
        console.warn('Web Speech API not supported in this browser.');
    }


    // --- Map Integration (Leaflet) ---
    if (mapid) {
        // Initialize the map only once
        mymap = L.map('mapid').setView([20.0, 0.0], 2); // Centered roughly on the world

        // Add a tile layer (OpenStreetMap)
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(mymap);

        // Handle map click event - still useful for getting coords or future features
        mymap.on('click', async (e) => {
             console.log("Map clicked at:", e.latlng);
             // Updated popup text to Vietnamese
             L.popup()
                 .setLatLng(e.latlng)
                 .setContent(`Vĩ độ: ${e.latlng.lat.toFixed(2)}<br>Kinh độ: ${e.latlng.lng.toFixed(2)}`)
                 .openOn(mymap);
         });

         // --- Map Filters (Optional - Keep if you want this feature) ---
         if (filterLanguageSelect) {
             // Example: Populate languages (fetch from backend or restcountries all)
             // For demo, let's hardcode a few common languages
             const languages = [
                 { code: 'eng', name: 'Tiếng Anh' },
                 { code: 'fra', name: 'Tiếng Pháp' },
                 { code: 'spa', name: 'Tiếng Tây Ban Nha' },
                 { code: 'zho', name: 'Tiếng Trung' },
                 { code: 'vie', name: 'Tiếng Việt' },
                 { code: 'rus', name: 'Tiếng Nga' },
                 // Add more languages
             ];
             languages.forEach(lang => {
                 const option = document.createElement('option');
                 option.value = lang.code;
                 option.textContent = lang.name;
                 filterLanguageSelect.appendChild(option);
             });

              filterLanguageSelect.addEventListener('change', (event) => {
                   const selectedLanguage = event.target.value;
                   console.log("Filtering map by language:", selectedLanguage);
                   // Implement filtering logic:
                   // 1. Fetch countries speaking this language from backend.
                   // 2. Clear existing markers/layers from map.
                   // 3. Add markers/highlight countries that match the filter.
                   alert(`Tính năng lọc bản đồ theo ngôn ngữ "${event.target.options[event.target.selectedIndex].text}" đang được phát triển.`);
              });
         }
    } else {
        console.error("Map container element #mapid not found!");
    }

    // --- History List (Simplified) ---
    // Load history when the page loads (using mock data initially)
    // In a real app, fetch from backend: loadHistoryFromBackend();
    // Using mock data for demonstration
    searchHistory.push({ query: "Dân số Việt Nam bao nhiêu?" });
    searchHistory.push({ query: "Thủ đô Thái Lan là gì?" });
    searchHistory.push({ query: "So sánh Pháp và Đức" });
    searchHistory.push({ query: "Thời tiết ở London?" });
    renderHistory(); // Initial render

    // No longer need specific history loading functions as it's updated on each send


}); // End DOMContentLoaded