// Lumina dashboard.
//
// Two things the previous version got wrong. User task text was written into
// the page with `<p>${text}</p>` -- unescaped -- so a student typing HTML (or
// a model echoing it) had it rendered; only the JSON branch was escaped. And
// the API base was the hardcoded `http://127.0.0.1:8000`, so the page worked
// only when opened next to a dev server on that exact port. The page is served
// by the API now, so requests are same-origin, and every value is escaped.

const chatForm = document.getElementById("chat-form");
const taskInput = document.getElementById("task-input");
const chatContainer = document.getElementById("chat-container");
const sendBtn = document.getElementById("send-btn");
const apiKeyInput = document.getElementById("api-key");

const sId = document.getElementById("student-id");
const sName = document.getElementById("student-name");
const grade = document.getElementById("grade-level");
const age = document.getElementById("age");
const styleSelect = document.getElementById("learning-style");

const KEY_STORAGE = "lumina.apiKey";
try {
    if (apiKeyInput) apiKeyInput.value = sessionStorage.getItem(KEY_STORAGE) || "";
} catch (e) { /* storage unavailable */ }
apiKeyInput?.addEventListener("input", () => {
    try { sessionStorage.setItem(KEY_STORAGE, apiKeyInput.value); } catch (e) { /* ignore */ }
});

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const task = taskInput.value.trim();
    if (!task) return;

    addMessage(task, "user");
    taskInput.value = "";

    const loadId = "msg-" + Date.now();
    addMessage("Orchestrator is working…", "system", loadId, "Orchestrator");
    taskInput.disabled = true;
    sendBtn.disabled = true;

    try {
        const payload = {
            task,
            student: {
                student_id: sId.value,
                name: sName.value,
                grade_level: grade.value,
                age: parseInt(age.value, 10),
                learning_style: styleSelect.value,
                language: "English",
            },
        };

        const res = await fetch("/api/v1/tutor/solve", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-API-Key": apiKeyInput ? apiKeyInput.value : "" },
            body: JSON.stringify(payload),
        });

        document.getElementById(loadId)?.remove();

        let data = null;
        try { data = await res.json(); } catch (err) { data = null; }

        if (res.ok && data && data.status === "success") {
            const responseText = typeof data.response === "object"
                ? JSON.stringify(data.response, null, 2)
                : data.response;
            const agent = String(data.agent_invoked || "agent").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
            addMessage(responseText, "system", null, agent, true);
        } else if (res.status === 401) {
            addMessage("Not authorised. Enter the API key in the sidebar.", "system", null, "System");
        } else {
            const detail = data && data.detail;
            const message = detail && typeof detail === "object" ? detail.message : (detail || "The task could not be processed.");
            const requestId = detail && typeof detail === "object" ? detail.request_id : null;
            addMessage(message + (requestId ? ` (ref ${requestId})` : ""), "system", null, "System");
        }
    } catch (err) {
        document.getElementById(loadId)?.remove();
        addMessage("Could not reach the API: " + err.message, "system", null, "System");
    } finally {
        taskInput.disabled = false;
        sendBtn.disabled = false;
        taskInput.focus();
    }
});

function addMessage(text, type, id = null, agent = null, isJson = false) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${type}-message fade-in`;
    if (id) msgDiv.id = id;

    const avatar = type === "system" ? "🤖" : "👤";
    const avatarClass = type === "system" ? "avatar-system" : "avatar-user";

    let contentHtml = "";
    if (type === "system" && agent) {
        contentHtml += `<span class="agent-tag">${escapeHtml(agent)}</span>`;
    }
    // Both branches escape: the transcript is untrusted, and so is a model
    // reply that a student's task could have shaped.
    contentHtml += isJson ? `<pre>${escapeHtml(text)}</pre>` : `<p>${escapeHtml(text)}</p>`;

    msgDiv.innerHTML = `<div class="${avatarClass}">${avatar}</div><div class="bubble">${contentHtml}</div>`;
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: "smooth" });
}
