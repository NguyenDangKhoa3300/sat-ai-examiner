// --- CONFIGURATION ---
const flatDomains = {
    "Information and Ideas": ["Central Ideas and Details", "Command of Evidence", "Inferences"],
    "Craft and Structure": ["Words in Context", "Text Structure and Purpose", "Cross-Text Connections"],
    "Expression of Ideas": ["Rhetorical Synthesis", "Transitions"],
    "Standard English Conventions": ["Boundaries", "Form, Structure, and Sense"]
};

const greetings = ["Ready to conquer SAT? 🚀", "Focus mode: ON! ⚡", "Mozart is boosting your IQ. 🧠"];
let isSoundOn = false; 
const bgMusic = document.getElementById('bgMusic');
if(bgMusic) bgMusic.volume = 0.3;

// --- 1. START SCREEN & LOGIN ---
const startAction = () => {
    const fName = document.getElementById('userFirstName').value.trim();
    const displayName = fName ? fName : "Scholar";
    
    document.getElementById('displayUserName').innerText = displayName;
    document.getElementById('greetingText').innerText = greetings[Math.floor(Math.random() * greetings.length)] + " 🎵";
    document.getElementById('startOverlay').classList.add('hidden'); 
    
    isSoundOn = true;
    bgMusic.play().catch(e => {});
    document.getElementById('soundClick').play().catch(e=>{});
};

document.getElementById('startBtn').addEventListener('click', startAction);

// Enter Key Support
document.querySelectorAll('#userFirstName, #userLastName').forEach(input => {
    input.addEventListener('keypress', (e) => { if (e.key === 'Enter') startAction(); });
});

// --- 2. LOGIC DROPDOWN ---
const dSelect = document.getElementById('domainSelect');
const tSelect = document.getElementById('topicSelect');

dSelect.innerHTML = '<option value="" disabled selected>Select Domain</option>';
for (const domain in flatDomains) dSelect.add(new Option(domain, domain));

dSelect.addEventListener('change', function() {
    tSelect.innerHTML = '<option value="" disabled selected>-- Choose a Topic --</option>';
    tSelect.disabled = false;
    tSelect.className = "w-full p-3 pl-4 bg-white border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/20 focus:outline-none transition shadow-sm appearance-none cursor-pointer text-slate-700 font-medium";
    flatDomains[this.value].forEach(t => tSelect.add(new Option(t, t)));
});

// --- 3. XỬ LÝ SUBMIT & PREDICT ---
document.getElementById('satForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    playClick(); 
    
    // Validation
    if (!tSelect.value || tSelect.disabled) { alert("⚠️ Select Domain/Topic!"); return; }
    if (!document.getElementById('questionText').value) { alert("⚠️ Enter Question!"); return; }

    // UI Change
    document.getElementById('welcomeState').classList.add('hidden');
    document.getElementById('resultState').classList.add('hidden');
    document.getElementById('loadingState').classList.remove('hidden'); 
    
    try {
        const response = await fetch('/api/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                child_topic: tSelect.value,
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

function showResult(result) {
    document.getElementById('loadingState').classList.add('hidden');
    document.getElementById('resultState').classList.remove('hidden');
    
    try {
        if (isSoundOn) document.getElementById('soundSuccess').play().catch(()=>{});
        confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
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
    
    bar.className = `h-full rounded-full transition-all duration-1500 w-0 ${color}`;
    requestAnimationFrame(() => { bar.style.width = `${(result.predicted_score_band / 7) * 100}%`; });
    
    readAloud(`Correct answer is ${result.correct_answer}. ${result.reasoning}`);

    // Hiện Popup sau 3s
    setTimeout(() => {
        const pop = document.getElementById('feedbackPopup');
        pop.classList.remove('hidden');
        try { if(isSoundOn) document.getElementById('soundPopup').play().catch(()=>{}); } catch(e){}
    }, 3000);
}

// --- 4. POPUP & FEEDBACK LOGIC ---
function closePopup() { document.getElementById('feedbackPopup').classList.add('hidden'); }
document.addEventListener('keydown', (e) => { if (e.key === "Escape") closePopup(); });

document.getElementById('correctBtn').addEventListener('click', () => {
    closePopup(); confetti({particleCount:50, spread:50}); 
});

document.getElementById('wrongBtn').addEventListener('click', () => {
    document.getElementById('feedbackChoices').classList.add('hidden');
    document.getElementById('correctionForm').classList.remove('hidden');
});

function selectBand(n) {
    document.getElementById('selectedCorrectBand').value = n;
    document.querySelectorAll('.band-btn').forEach(b => b.classList.remove('bg-blue-600', 'text-white'));
    event.target.classList.add('bg-blue-600', 'text-white');
}
window.selectBand = selectBand; // Expose global
window.closePopup = closePopup;

document.getElementById('submitCorrectionBtn').addEventListener('click', async () => {
    const band = document.getElementById('selectedCorrectBand').value;
    if(!band) { alert("Please select the correct band!"); return; }
    
    try {
        const res = await fetch('/api/feedback', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({
                child_topic: tSelect.value,
                question_text: document.getElementById('questionText').value,
                option_a: document.getElementById('optA').value, 
                option_b: document.getElementById('optB').value,
                option_c: document.getElementById('optC').value, 
                option_d: document.getElementById('optD').value,
                correct_band: parseInt(band)
            })
        });
        if(res.ok) {
            alert("Thanks! Feedback Saved & AI Updated.");
            closePopup();
            document.getElementById('feedbackChoices').classList.remove('hidden');
            document.getElementById('correctionForm').classList.add('hidden');
        } else { alert("Failed to save feedback."); }
    } catch(e) { alert("Error connecting to server."); }
});

// --- 5. RESET FORM (Hiệu ứng bốc hơi) ---
document.getElementById('resetBtn').addEventListener('click', () => {
    playClick();
    window.speechSynthesis.cancel();
    const inputs = document.querySelectorAll('#satForm input, #satForm textarea');
    inputs.forEach(el => el.classList.add('evaporate-text'));

    setTimeout(() => {
        document.getElementById('satForm').reset();
        inputs.forEach(el => el.classList.remove('evaporate-text'));
        document.getElementById('resultState').classList.add('hidden');
        document.getElementById('welcomeState').classList.remove('hidden');
        closePopup(); 
        tSelect.innerHTML = '<option value="" disabled selected>Waiting...</option>';
        tSelect.disabled = true;
        tSelect.className = "w-full p-3 pl-4 bg-slate-100 border border-transparent rounded-xl focus:ring-4 focus:ring-blue-500/20 focus:outline-none transition appearance-none cursor-not-allowed text-slate-400 font-medium";
    }, 600);
});

// --- 6. UTILS (Sound, TTS) ---
document.getElementById('toggleSoundBtn').addEventListener('click', function() {
    isSoundOn = !isSoundOn;
    if (isSoundOn) {
        this.innerHTML = '<i class="fa-solid fa-music"></i> <span>Music On</span>';
        this.classList.replace('text-blue-600', 'text-green-600');
        bgMusic.play();
    } else {
        this.innerHTML = '<i class="fa-solid fa-volume-xmark"></i> <span>Music Off</span>';
        this.classList.replace('text-green-600', 'text-blue-600');
        bgMusic.pause();
        window.speechSynthesis.cancel();
    }
});

function playClick() {
    if (isSoundOn) {
        const s = document.getElementById('soundClick');
        s.currentTime = 0; s.volume = 0.3; s.play().catch(e=>{});
    }
}
document.querySelectorAll('input, select, button, textarea').forEach(el => el.addEventListener('mousedown', playClick));

let voices = [];
function loadVoices() { voices = window.speechSynthesis.getVoices(); }
window.speechSynthesis.onvoiceschanged = loadVoices;

const readAloud = (text) => {
    if (!isSoundOn) return;
    window.speechSynthesis.cancel();
    bgMusic.volume = 0.05; 
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US'; utterance.rate = 1.1;
    if (voices.length > 0) {
        const voice = voices.find(v => v.name.includes("Google US English") || v.name.includes("Zira"));
        if (voice) utterance.voice = voice;
    }
    utterance.onend = () => { bgMusic.volume = 0.3; };
    window.speechSynthesis.speak(utterance);
};

document.getElementById('replayVoiceBtn').addEventListener('click', () => {
    playClick();
    readAloud(`Correct answer is ${document.getElementById('correctAnswerDisplay').innerText}. ${document.getElementById('reasoningText').innerText}`);
});
loadVoices();

// --- 7. CHATBOT LOGIC (NEW) ---
const chatToggleBtn = document.getElementById('chatToggleBtn');
const chatWindow = document.getElementById('chatWindow');
const closeChatBtn = document.getElementById('closeChatBtn');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const chatMessages = document.getElementById('chatMessages');
let chatHistory = [];

function toggleChat() {
    chatWindow.classList.toggle('translate-y-[120%]');
    if (!chatWindow.classList.contains('translate-y-[120%]')) chatInput.focus();
}
if(chatToggleBtn) chatToggleBtn.addEventListener('click', toggleChat);
if(closeChatBtn) closeChatBtn.addEventListener('click', toggleChat);

function addMessage(text, isUser) {
    const div = document.createElement('div');
    div.className = `flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`;
    const avatar = isUser 
        ? '<div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm flex-shrink-0">👤</div>'
        : '<div class="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center text-lg flex-shrink-0">🤖</div>';
    const bubbleStyle = isUser ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-white text-slate-600 border border-slate-100 rounded-tl-none shadow-sm';
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
        
        // Loading Bubble
        const loadingId = 'loading-' + Date.now();
        const loadingDiv = document.createElement('div');
        loadingDiv.id = loadingId;
        loadingDiv.className = 'flex gap-3';
        loadingDiv.innerHTML = `<div class="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center text-lg">🤖</div><div class="bg-white p-3 rounded-2xl rounded-tl-none shadow-sm border border-slate-100 text-xs text-slate-400">Typing...</div>`;
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
            chatHistory.push({role: 'user', content: msg}, {role: 'model', content: data.reply});
        } catch (err) {
            document.getElementById(loadingId).remove();
            addMessage("Zimi is offline temporarily! 🥺", false);
        }
    });
}