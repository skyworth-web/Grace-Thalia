(function () {
    console.log("[CoPilot] overlay UI loaded");

    function createOverlay() {
        if (document.getElementById("copilot-overlay")) return;

        // ---------- CONTAINER ----------
        const box = document.createElement("div");
        box.id = "copilot-overlay";

        Object.assign(box.style, {
            position: "fixed",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: "1000px",
            height: "674px",
            background: "rgba(20, 20, 20, 0.65)",
            color: "white",
            borderRadius: "16px",
            zIndex: "2147483647",
            boxShadow: "0 10px 40px rgba(0,0,0,0.6)",
            display: "flex",
            flexDirection: "column",
            padding: "16px",
            border: "1px solid rgba(255,255,255,0.15)",
            cursor: "default",
        });

        // ---------- MAKE DRAGGABLE ----------
        let isDragging = false;
        let offsetX = 0;
        let offsetY = 0;

        box.addEventListener("mousedown", (e) => {
            if (e.target.classList.contains("copilot-header")) {
                isDragging = true;
                offsetX = e.clientX - box.getBoundingClientRect().left;
                offsetY = e.clientY - box.getBoundingClientRect().top;
            }
        });

        document.addEventListener("mousemove", (e) => {
            if (isDragging) {
                box.style.left = `${e.clientX - offsetX}px`;
                box.style.top = `${e.clientY - offsetY}px`;
                box.style.transform = "none";
            }
        });

        document.addEventListener("mouseup", () => {
            isDragging = false;
        });

        // ---------- UI HTML ----------
        // Inside createOverlay()
box.innerHTML = `
<div class="copilot-header" style="
    display:flex;
    justify-content:space-between;
    align-items:center;
    padding-bottom:6px;
    cursor:move;
">
    <strong style="font-size:16px;">🧠 Interview Co-Pilot+</strong>
    <button id="copilot-close" style="
        background:transparent;
        color:white;
        border:none;
        font-size:20px;
        cursor:pointer;
        opacity:0.7;
    ">×</button>
</div>

<div id="copilot-answer" style="
    padding:6px 0;
    font-size:20px;
    white-space:pre-wrap;
    border-bottom: 1px solid rgba(255,255,255,0.3); /* thin line */
    overflow-y:auto;
    max-height:150px;
"></div>

<div id="copilot-transcript" style="
    flex:1;
    padding:6px 0;
    font-size:18px;
    white-space:pre-wrap;
    overflow-y:auto;
">Listening…</div>

<div style="
    display:flex;
    gap:10px;
    flex-shrink:0;
    margin-top:8px;
">
    <button id="copilot-clear" style="
        flex:1;
        background:#ff4d4d;
        border:none;
        padding:10px;
        border-radius:8px;
        cursor:pointer;
        font-weight:600;
        color:white;
    ">Clear</button>

    <button id="copilot-generate" style="
        flex:1;
        background:#4caf50;
        border:none;
        padding:10px;
        border-radius:8px;
        cursor:pointer;
        font-weight:600;
        color:white;
    ">Generate</button>
</div>
`;


        document.body.appendChild(box);

        // ---------- UI ELEMENTS ----------
        const transcriptDiv = box.querySelector("#copilot-transcript");
        const answerDiv = box.querySelector("#copilot-answer");
        const clearBtn = box.querySelector("#copilot-clear");
        const generateBtn = box.querySelector("#copilot-generate");
        const closeBtn = box.querySelector("#copilot-close");

        let transcriptText = "";
        let streamedAnswer = "";

        // ---------- PUBLIC FUNCTIONS ----------
        window.__copilotUpdateTranscript = function (text) {
            transcriptText += " " + text;
            if (transcriptText.length > 8000)
                transcriptText = transcriptText.slice(transcriptText.length - 8000);

            transcriptDiv.textContent = transcriptText.trim();
            transcriptDiv.scrollTop = transcriptDiv.scrollHeight; // Always scroll to bottom
        };

        window.__copilotStreamAnswer = function (chunk) {
            streamedAnswer += chunk;
            answerDiv.style.display = "block";
            answerDiv.textContent = streamedAnswer;
            answerDiv.scrollTop = 0; // Keep answer at top
        };

        // ---------- BUTTON HANDLERS ----------
        clearBtn.onclick = () => {
            transcriptText = "";
            streamedAnswer = "";
            transcriptDiv.textContent = "Listening…";
            answerDiv.style.display = "none";
            answerDiv.textContent = "";
        };

        generateBtn.onclick = async () => {
            streamedAnswer = "";
            answerDiv.style.display = "block";
            answerDiv.textContent = "";
        
            const res = await fetch("http://localhost:8000/generate-stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ transcript: transcriptText }),
            });
        
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
        
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                streamedAnswer += chunk;
                answerDiv.textContent = streamedAnswer;
            }
        };
        

        closeBtn.onclick = () => box.style.display = "none";
    }

    // Create overlay immediately
    if (document.readyState === "loading")
        document.addEventListener("DOMContentLoaded", createOverlay);
    else
        createOverlay();
})();
