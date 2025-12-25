// --- 1. CONFIGURATION & DATA ---
const flatDomains = {
    "Information and Ideas": ["Central Ideas and Details", "Command of Evidence", "Inferences"],
    "Craft and Structure": ["Words in Context", "Text Structure and Purpose", "Cross-Text Connections"],
    "Expression of Ideas": ["Rhetorical Synthesis", "Transitions"],
    "Standard English Conventions": ["Boundaries", "Form, Structure, and Sense"]
};

let isSoundOn = false; 
const bgMusic = document.getElementById('bgMusic');
if(bgMusic) bgMusic.volume = 0.3;

// --- 2. CORE FUNCTIONS ---
function playClick() {
    if (isSoundOn) {
        const s = document.getElementById('soundClick');
        if(s) { s.currentTime = 0; s.volume = 0.3; s.play().catch(e=>{}); }
    }
}

function initAudio() {
    if(!isSoundOn && bgMusic) {
        isSoundOn = true;
        bgMusic.play().catch(e => console.log("Blocked"));
        const btn = document.getElementById('toggleSoundBtn');
        if(btn) {
            btn.innerHTML = '<i class="fa-solid fa-music"></i> Music On';
            btn.classList.replace('text-slate-400', 'text-green-600');
            btn.classList.add('border-green-200', 'bg-green-50');
        }
    }
}

// --- 3. LOGIC CHO TRANG WORKSPACE ---
// (Chạy khi trang Workspace tải xong)
const domainSelect = document.getElementById('domainSelect');

if (domainSelect) {
    console.log("🚀 Initializing Workspace...");
    document.body.addEventListener('click', initAudio, { once: true });

    // A. Nạp dữ liệu vào Dropdown
    domainSelect.innerHTML = '<option value="" disabled selected>Select Domain</option>';
    for (const domain in flatDomains) {
        domainSelect.add(new Option(domain, domain));
    }

    const topicSelect = document.getElementById('topicSelect');
    
    // Sự kiện khi chọn Domain
    domainSelect.addEventListener('change', function() {
        playClick();
        topicSelect.innerHTML = '<option value="" disabled selected>-- Choose a Topic --</option>';
        topicSelect.disabled = false;
        topicSelect.className = "w-full p-3 pl-4 bg-white border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition shadow-sm text-blue-700 font-medium";
        
        if(flatDomains[this.value]) {
            flatDomains[this.value].forEach(t => topicSelect.add(new Option(t, t)));
        }
        
        topicSelect.parentElement.classList.add('animate-pulse');
        setTimeout(() => topicSelect.parentElement.classList.remove('animate-pulse'), 500);
    });

    // --- LOGIC NHẬN DỮ LIỆU CLONE TỪ LIBRARY ---
    const cloneDataJson = localStorage.getItem('zim_clone_data');
    if (cloneDataJson) {
        try {
            const cloneData = JSON.parse(cloneDataJson);
            console.log("📥 Receiving Clone Data:", cloneData);

            // Tự động tìm Domain
            let foundDomain = cloneData.parent_topic;
            let isDomainValid = false;
            
            if (foundDomain && flatDomains[foundDomain]) {
                isDomainValid = true;
            } else {
                for (const [domain, topics] of Object.entries(flatDomains)) {
                    if (topics.includes(cloneData.child_topic)) {
                        foundDomain = domain;
                        isDomainValid = true;
                        break;
                    }
                }
            }

            if (isDomainValid) {
                domainSelect.value = foundDomain;
                domainSelect.dispatchEvent(new Event('change'));
                setTimeout(() => { if(topicSelect) topicSelect.value = cloneData.child_topic; }, 50);
            }

            if(document.getElementById('questionText')) {
                document.getElementById('questionText').value = cloneData.question_text || "";
                document.getElementById('optA').value = cloneData.option_a || "";
                document.getElementById('optB').value = cloneData.option_b || "";
                document.getElementById('optC').value = cloneData.option_c || "";
                document.getElementById('optD').value = cloneData.option_d || "";
                
                setTimeout(() => {
                    document.getElementById('questionText').classList.add('animate-pulse');
                    document.getElementById('questionText').focus();
                    try { confetti({ particleCount: 60, spread: 50, origin: { y: 0.3 }, colors: ['#a855f7', '#d8b4fe'] }); } catch(e){}
                }, 300);
            }
            localStorage.removeItem('zim_clone_data');
        } catch (e) { console.error("Clone error:", e); }
    }

    // B. Xử lý Submit (Dự đoán 1 câu)
    const satForm = document.getElementById('satForm');
    if(satForm) {
        satForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            playClick();
            
            if (!topicSelect.value || topicSelect.disabled) { alert("⚠️ Please select both Domain and Topic!"); return; }
            if (!document.getElementById('questionText').value.trim()) { alert("⚠️ Please enter the question content!"); return; }

            document.getElementById('welcomeState').classList.add('hidden');
            document.getElementById('resultState').classList.add('hidden');
            document.getElementById('loadingState').classList.remove('hidden'); 
            
            try {
                const response = await fetch('/api/predict', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        child_topic: topicSelect.value,
                        question_text: document.getElementById('questionText').value,
                        option_a: document.getElementById('optA').value,
                        option_b: document.getElementById('optB').value,
                        option_c: document.getElementById('optC').value,
                        option_d: document.getElementById('optD').value
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail);
                setTimeout(() => showResult(result), 1500);
            } catch (error) {
                alert("Error: " + error.message);
                document.getElementById('loadingState').classList.add('hidden');
                document.getElementById('welcomeState').classList.remove('hidden');
            }
        });
    }

    // C. Xử lý Reset
    const resetBtn = document.getElementById('resetBtn');
    if(resetBtn) {
        resetBtn.addEventListener('click', () => {
            playClick();
            window.speechSynthesis.cancel();
            satForm.reset();
            const resultBox = document.getElementById('resultState');
            resultBox.classList.add('evaporate-text');
            setTimeout(() => {
                resultBox.classList.remove('evaporate-text', 'hidden'); 
                resultBox.classList.add('hidden'); 
                document.getElementById('welcomeState').classList.remove('hidden'); 
                document.getElementById('welcomeState').classList.add('fade-in');
            }, 300);
            topicSelect.innerHTML = '<option value="" disabled selected>Waiting...</option>';
            topicSelect.disabled = true;
            topicSelect.className = "w-full p-3 pl-4 bg-slate-100/80 rounded-xl transition";
        });
    }
} // <--- ĐÓNG IF(DOMAINSELECT) TẠI ĐÂY LÀ ĐÚNG

// --- 4. CÁC HÀM HỖ TRỢ HIỂN THỊ ---
function showResult(result) {
    document.getElementById('loadingState').classList.add('hidden');
    document.getElementById('resultState').classList.remove('hidden');
    try {
        if (isSoundOn) document.getElementById('soundSuccess').play().catch(()=>{});
        confetti({ particleCount: 150, spread: 80, origin: { y: 0.6 }, gravity: 0.8 });
    } catch(e) {}

    document.getElementById('correctAnswerDisplay').innerText = result.correct_answer || "Unknown";
    document.getElementById('scoreNum').innerText = result.predicted_score_band;
    document.getElementById('reasoningText').innerText = result.reasoning;
    document.getElementById('scoreLabel').innerText = result.predicted_label;
    
    const bar = document.getElementById('scoreBar');
    let color = "bg-blue-500";
    if (result.predicted_label === "Easy") color = "bg-emerald-500";
    else if (result.predicted_label === "Medium") color = "bg-amber-500";
    else if (result.predicted_label === "Hard") color = "bg-rose-600";
    
    bar.className = `h-full rounded-full transition-all duration-1500 w-0 shadow-lg ${color}`;
    requestAnimationFrame(() => { bar.style.width = `${(result.predicted_score_band / 7) * 100}%`; });
    readAloud(`Analysis complete. The correct answer is ${result.correct_answer}. Predicted Band: ${result.predicted_score_band}.`);

    setTimeout(() => {
        const pop = document.getElementById('feedbackPopup');
        if(pop) pop.classList.remove('hidden');
    }, 3000);
}

// --- 5. LOGIC POPUP FEEDBACK ---
function closePopup() { document.getElementById('feedbackPopup').classList.add('hidden'); }
document.addEventListener('keydown', (e) => { if (e.key === "Escape") closePopup(); });

const correctBtn = document.getElementById('correctBtn');
if(correctBtn) {
    correctBtn.addEventListener('click', () => {
        closePopup(); 
        confetti({particleCount:50, spread:50, origin: { y: 0.5 }}); 
    });
}

const wrongBtn = document.getElementById('wrongBtn');
if(wrongBtn) {
    wrongBtn.addEventListener('click', () => {
        document.getElementById('feedbackChoices').classList.add('hidden');
        document.getElementById('correctionForm').classList.remove('hidden');
    });
}

window.selectBand = function(n) {
    document.getElementById('selectedCorrectBand').value = n;
    document.querySelectorAll('.band-btn').forEach(b => {
        b.classList.remove('bg-blue-600', 'text-white', 'ring-2', 'ring-blue-300');
        b.classList.add('bg-white', 'hover:bg-blue-600', 'hover:text-white');
    });
    event.target.classList.remove('bg-white', 'hover:bg-blue-600', 'hover:text-white');
    event.target.classList.add('bg-blue-600', 'text-white', 'ring-2', 'ring-blue-300');
}
window.closePopup = closePopup;

const submitCorrectionBtn = document.getElementById('submitCorrectionBtn');
if(submitCorrectionBtn) {
    submitCorrectionBtn.addEventListener('click', async () => {
        const band = document.getElementById('selectedCorrectBand').value;
        if(!band) { alert("Please select the correct band score!"); return; }
        
        const originalText = submitCorrectionBtn.innerText;
        submitCorrectionBtn.innerText = "Saving...";
        submitCorrectionBtn.disabled = true;

        try {
            const res = await fetch('/api/feedback', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({
                    child_topic: document.getElementById('topicSelect').value,
                    question_text: document.getElementById('questionText').value,
                    option_a: document.getElementById('optA').value, 
                    option_b: document.getElementById('optB').value,
                    option_c: document.getElementById('optC').value, 
                    option_d: document.getElementById('optD').value,
                    correct_band: parseInt(band)
                })
            });
            if(res.ok) {
                alert("✨ Thanks teacher! Feedback Saved & AI Updated.");
                closePopup();
                document.getElementById('feedbackChoices').classList.remove('hidden');
                document.getElementById('correctionForm').classList.add('hidden');
            } else { alert("Failed to save feedback."); }
        } catch(e) { alert("Error connecting to server."); } 
        finally {
            submitCorrectionBtn.innerText = originalText;
            submitCorrectionBtn.disabled = false;
        }
    });
}

// --- 6. LOGIC CHATBOT ZIMI ---
const chatToggleBtn = document.getElementById('chatToggleBtn');
const chatWindow = document.getElementById('chatWindow');
const closeChatBtn = document.getElementById('closeChatBtn');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const chatMessages = document.getElementById('chatMessages');
let chatHistory = [];

function toggleChat() {
    chatWindow.classList.toggle('translate-y-[120%]');
    if (!chatWindow.classList.contains('translate-y-[120%]')) {
        chatInput.focus();
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

if(chatToggleBtn) {
    chatToggleBtn.addEventListener('click', toggleChat);
    closeChatBtn.addEventListener('click', toggleChat);
}

function addMessage(text, isUser) {
    const div = document.createElement('div');
    div.className = `flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`;
    const avatar = isUser ? '<div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm flex-shrink-0 border border-blue-200">👤</div>' : '<div class="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center text-lg flex-shrink-0 border border-purple-200">🤖</div>';
    const bubbleStyle = isUser ? 'bg-blue-600 text-white rounded-tr-none shadow-md' : 'bg-white text-slate-600 border border-slate-100 rounded-tl-none shadow-sm';
    div.innerHTML = `${avatar}<div class="${bubbleStyle} p-3 rounded-2xl text-sm max-w-[80%] leading-relaxed animate-fade-in-up">${text}</div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

if(chatForm) {
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const msg = chatInput.value.trim();
        if (!msg) return;
        addMessage(msg, true);
        chatInput.value = '';
        
        const loadingId = 'loading-' + Date.now();
        const loadingDiv = document.createElement('div');
        loadingDiv.id = loadingId;
        loadingDiv.className = 'flex gap-3';
        loadingDiv.innerHTML = `<div class="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center text-lg border border-purple-200">🤖</div><div class="bg-white p-3 rounded-2xl rounded-tl-none shadow-sm border border-slate-100 text-xs text-slate-400 flex items-center gap-1">Zimi is thinking <span class="animate-bounce">.</span><span class="animate-bounce delay-75">.</span><span class="animate-bounce delay-150">.</span></div>`;
        chatMessages.appendChild(loadingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message: msg, history: chatHistory.slice(-6) })
            });
            const data = await res.json();
            document.getElementById(loadingId).remove();
            addMessage(data.reply, false);
            chatHistory.push({role: 'user', content: msg});
            chatHistory.push({role: 'model', content: data.reply});
        } catch (err) {
            if(document.getElementById(loadingId)) document.getElementById(loadingId).remove();
            addMessage("Opps! My connection is weak. Try again? 🥺", false);
        }
    });
}

// --- 7. UTILS ---
const toggleSoundBtn = document.getElementById('toggleSoundBtn');
if(toggleSoundBtn) {
    toggleSoundBtn.addEventListener('click', function() {
        isSoundOn = !isSoundOn;
        if (isSoundOn) {
            this.innerHTML = '<i class="fa-solid fa-music"></i> Music On';
            this.classList.replace('text-slate-400', 'text-green-600'); 
            this.classList.add('border-green-200', 'bg-green-50');
            if(bgMusic) bgMusic.play().catch(e=>{});
        } else {
            this.innerHTML = '<i class="fa-solid fa-volume-xmark"></i> Music Off';
            this.classList.replace('text-green-600', 'text-slate-400');
            this.classList.remove('border-green-200', 'bg-green-50');
            if(bgMusic) bgMusic.pause();
            window.speechSynthesis.cancel();
        }
    });
}

document.addEventListener('mousedown', (e) => {
    if(e.target.closest('button') || e.target.closest('a') || e.target.closest('input') || e.target.closest('select')) playClick();
});

let voices = [];
function loadVoices() { voices = window.speechSynthesis.getVoices(); }
window.speechSynthesis.onvoiceschanged = loadVoices;

const readAloud = (text) => {
    if (!isSoundOn) return;
    window.speechSynthesis.cancel();
    if(bgMusic) bgMusic.volume = 0.05; 
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US'; utterance.rate = 1.1;
    if (voices.length > 0) {
        const voice = voices.find(v => v.name.includes("Google US English") || v.name.includes("Zira"));
        if (voice) utterance.voice = voice;
    }
    utterance.onend = () => { if(bgMusic) bgMusic.volume = 0.3; }; 
    window.speechSynthesis.speak(utterance);
};

const replayVoiceBtn = document.getElementById('replayVoiceBtn');
if(replayVoiceBtn) {
    replayVoiceBtn.addEventListener('click', () => {
        playClick();
        readAloud(`The correct answer is ${document.getElementById('correctAnswerDisplay').innerText}. ${document.getElementById('reasoningText').innerText}`);
    });
}
loadVoices();

// --- [UPDATED] BATCH UPLOAD FUNCTION (GLOBAL SCOPE) ---
// Hàm này phải nằm ngoài cùng (KHÔNG ĐƯỢC nằm trong if(domainSelect))
async function uploadExcel() {
    const fileInput = document.getElementById('excelInput');
    const file = fileInput.files[0];
    
    if (!file) return;

    const loadingModal = document.getElementById('batchLoading');
    if(loadingModal) {
        loadingModal.classList.remove('hidden');
        const h3 = loadingModal.querySelector('h3');
        if(h3) h3.innerText = "AI is Processing...";
    }
    
    playClick();

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/batch-predict', {
            method: 'POST',
            body: formData
        });

        // Kiểm tra content-type để biết là file hay lỗi JSON
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            const errData = await response.json();
            throw new Error(errData.detail || "Server Error");
        }

        if (!response.ok) throw new Error("Upload failed: " + response.statusText);

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `AI_Result_${new Date().getTime()}.xlsx`;
        document.body.appendChild(a);
        a.click();
        a.remove();

        if(loadingModal) loadingModal.classList.add('hidden');
        alert("✅ Completed! Please check the downloaded file.");
        try { confetti({ particleCount: 200, spread: 120, origin: { y: 0.6 } }); } catch(e){}

    } catch (error) {
        if(loadingModal) loadingModal.classList.add('hidden');
        console.error(error);
        alert("❌ OOPS: " + error.message);
    } finally {
        fileInput.value = '';
    }
}