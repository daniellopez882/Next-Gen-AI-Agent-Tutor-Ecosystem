<div align="center">
  
# � LUMINA AI
### **The Autonomous Multi-Agent Orchestration Engine for Hyper-Personalized Mastery**

**A paradigm shift in EdTech architecture built on the Model Context Protocol (MCP)**

[![Status: Production Ready](https://img.shields.io/badge/Status-Production--Ready-06b6d4.svg)](#)
[![Stack: MCP Native](https://img.shields.io/badge/Stack-MCP--Native-3b82f6.svg)](#)
[![Orchestrator: LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph-05070a.svg)](#)
[![Agents: CrewAI](https://img.shields.io/badge/Agents-CrewAI-cyan.svg)](#)

</div>

---

## ⚡ The Thesis: Beyond Static Learning

In the Silicon Valley of 2026, we don't build "apps." We build **Autonomous Ecosystems**. 

Legacy EdTech platforms are failing because they rely on linear curricula and single-inference LLMs. They lack memory, pedagogical structure, and the ability to pivot based on student frustration.

**Lumina** is our answer. It is a **Stateful Multi-Agent Workflow** that treats every student as a unique data point. By leveraging **LangGraph** as a central cognitive supervisor and **CrewAI** as specialized execution units, Lumina builds a living, breathing digital tutor that lives inside your IDE, your browser, or your desktop.

---

## 🏗️ Architectural Excellence

Lumina isn't just a chatbot; it's a modular, event-driven orchestration stack designed for scale:

- **🧠 Cognitive Supervisor**: `LangGraph` handles state management and intent classification.
- **🚀 Execution Swarm**: `CrewAI` agents (Lesson Architect, Doubt Resolver, Assessment Engine) operate in specialized cycles.
- **🔌 Protocol Layer**: Full `Model Context Protocol (MCP)` native support. Bridge your tutor directly into Claude Desktop.
- **💾 Mastery Core**: Persistent `SQLite` + `ChromaDB` Vector RAG ensures every response is grounded in actual curriculum, not LLM hallucinations.
- **🎨 Elite Interface**: Zero-latency, glassmorphic UI built for the modern attention span.

---

## � The Tech Stack (The "Secret Sauce")

- **Statefulness**: `LangGraph` (Infinite context loops)
- **Specialization**: `CrewAI` (Multi-role agent teams)
- **Knowledge**: `RAG` (Retrieval Augmented Generation via Vector Embeddings)
- **Interoperability**: `MCP` (Anthropic's standardized data protocol)
- **Persistence**: `SQLAlchemy` (Longitudinal student performance tracking)

---

## � Rapid Deployment

### **1. Spin up the Core**
```bash
# Clone and enter the nexus
python -m venv venv
# On Windows
.\venv\Scripts\Activate.ps1
```

### **2. Hydrate the Environment**
```bash
pip install -r requirements.txt
```

### **3. Configure Your Foundation Models**
Set up your `.env` with the high-reasoning tokens:
```env
ANTHROPIC_API_KEY="sk-ant-..."
OPENAI_API_KEY="sk-proj-..."
```

---

## 🧩 Modalities of Engagement

### **A. The Browser Experience**
Run the backend orchestrator:
```bash
uvicorn main:app --reload
```
Launch `frontend/index.html` to enter the glassmorphic Lumina interface.

### **B. The MCP Integration (The "Power Move")**
Lumina is a first-class citizen of the MCP world. Integrate it directly into **Claude Desktop**:
```json
{
  "mcpServers": {
    "lumina-agent": {
      "command": "C:/path/to/venv/Scripts/python.exe",
      "args": ["C:/path/to/mcp_server.py"]
    }
  }
}
```

---

## 📜 The Roadmap: To AGI Education

- [ ] Multi-Modal Visual Tutoring (Solving math via camera)
- [ ] Group Learning Orchestration (Agents managing student cohorts)
- [ ] Direct Notion/Canvas/Blackboard API synchronization

---

**Built by Lumina Architects for the Next Billion Learners. 🚀**
*(Personalized & Re-Engineered)*
