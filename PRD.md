Below is a **formal, clean PRD + SRD-lite** suitable for stakeholders, investors, and engineers.
This is written as a **single cohesive document** (not notes), with clear separation of concerns.

---

# HybridFlow

**Product Requirements Document (PRD) & Software Requirements Document – Lite (SRD-Lite)**
**Version:** 0.1 (MVP)
**Status:** Approved for implementation

---

## 1. Product Requirements Document (PRD)

### 1.1 Product Overview

HybridFlow is a **WhatsApp AI automation platform** designed to automate customer conversations while preserving seamless human control. The system ensures that AI and humans never collide in the same conversation by enforcing a strict session-level state machine.

HybridFlow acts as a **control plane** between WhatsApp (via Evolution API), AI models, and business owners.

---

### 1.2 Problem Statement

Most WhatsApp automation tools suffer from **message collision**:

* AI replies while a human is typing
* Duplicate or conflicting messages
* Loss of trust in automation

Business owners want automation **without losing authority or timing control**.

---

### 1.3 Target Users

**Primary users**

* Small & medium businesses (SMBs)
* Solo founders and service providers
* E-commerce merchants
* Real estate and high-intent lead businesses

**Secondary users**

* Automation consultants
* Agencies managing WhatsApp for clients

---

### 1.4 Core Value Proposition

1. **Invisible Human Takeover**
   When a business owner replies manually, AI automatically pauses for that contact without notifying the customer.

2. **Reliable Automation Control**
   AI replies only when explicitly allowed by the session state.

3. **Multi-Tenant Architecture**
   One platform supports multiple WhatsApp instances and businesses.

---

### 1.5 MVP Features

#### F1. WhatsApp Session Automation

* Receive inbound WhatsApp messages via Evolution API
* Send AI-generated replies back to WhatsApp

#### F2. Invisible Mute (Anti-Collision)

* Detect `fromMe=true` messages
* Pause automation for that chat immediately
* Resume automatically after inactivity or manually

#### F3. Session State Tracking

Each chat session tracks:

* paused / active state
* last human interaction timestamp
* last message timestamp

#### F4. Manual Resume

* Business owner or system can manually resume a paused session

#### F5. Multi-Tenant Routing

* Route all events using `instance_name`
* Each tenant has isolated data, prompts, and settings

---

### 1.6 Success Metrics

* **0% collision rate** (AI never replies while human is active)
* **>70% automated resolution rate** for inbound queries
* **<1s webhook acknowledgment time**
* **100% webhook delivery reliability**

---

### 1.7 Out of Scope (MVP)

* Customer-facing chat UI
* Agent inbox
* Payments / billing
* Full CRM features
* Voice calls (text only initially)

---

## 2. Software Requirements Document – Lite (SRD-Lite)

### 2.1 System Architecture

```
WhatsApp
   ↓
Evolution API (Baileys)
   ↓ Webhooks
HybridFlow API (FastAPI)
   ↓
Supabase Postgres
   ↓
LLM Provider
   ↓
Evolution API → WhatsApp
```

---

### 2.2 Technology Stack

| Layer                    | Technology                   |
| ------------------------ | ---------------------------- |
| WhatsApp Gateway         | Evolution API                |
| Backend Control Plane    | FastAPI (Python)             |
| Database                 | Supabase (Postgres)          |
| AI                       | OpenAI / Mistral / Anthropic |
| Hosting                  | Railway                      |
| Orchestration (optional) | n8n (testing only)           |
| Alerts (optional)        | Telegram Bot                 |

---

### 2.3 Core Data Models

#### Tenant

Represents one business / WhatsApp instance.

* instance_name (unique)
* Evolution API credentials
* system prompt
* LLM provider settings

#### Session

Represents one WhatsApp chat thread.

* tenant_id
* chat_id (remoteJid)
* is_paused
* last_human_at
* last_message_at

#### Message

Audit log of WhatsApp messages.

* message_id
* chat_id
* from_me
* text
* raw_payload

---

### 2.4 Session State Machine

| Condition                     | Action             |
| ----------------------------- | ------------------ |
| Customer message + active     | AI reply allowed   |
| Owner message (`fromMe=true`) | Pause session      |
| Customer message + paused     | Ignore             |
| Inactivity > 2h               | Auto-resume        |
| Manual resume                 | Resume immediately |

---

### 2.5 External Integrations

#### Evolution API

* Inbound webhooks for WhatsApp events
* Outbound REST API for sending messages

#### Supabase

* Persistent storage
* Scheduled job for auto-resume

#### LLM Provider

* Chat completion
* Optional classification (later)

---

### 2.6 API Contract (HybridFlow)

#### 2.6.1 Inbound Webhook

`POST /webhooks/evolution`

**Purpose**
Receives all WhatsApp events from Evolution API.

**Required Fields**

```json
{
  "event": "messages.upsert",
  "instance": "test-02",
  "data": {
    "key": {
      "remoteJid": "2349...@s.whatsapp.net",
      "fromMe": false,
      "id": "msg-id"
    },
    "message": { "conversation": "text" }
  }
}
```

**Behavior**

* Resolve tenant by `instance`
* Upsert session
* Log message
* Apply collision rules
* Enqueue or block AI reply

---

#### 2.6.2 Session Status

`GET /sessions/{instance}/{chat_id}`

Returns current automation state.

---

#### 2.6.3 Manual Resume

`POST /sessions/{instance}/{chat_id}/resume`

Resumes automation for a chat.

---

### 2.7 Non-Functional Requirements

* Webhook processing must be idempotent
* Stateless FastAPI instances
* All critical state stored in DB
* AI replies must never block webhook acknowledgment
* Secrets stored server-side only

---

### 2.8 Security (MVP)

* Evolution API key verification
* Instance-based isolation
* Service-role access to DB
* HTTPS only

---

### 2.9 Deployment Strategy

* Evolution API: Railway (Docker image)
* HybridFlow API: Railway (FastAPI)
* Supabase: Managed
* Domain: Railway or Cloudflare

---

### 2.10 MVP Build Order

1. Supabase schema
2. FastAPI webhook ingestion
3. Session state logic
4. Outbound message send
5. Auto-resume job
6. Basic monitoring/logging

---

## 3. Implementation Readiness

This document is **implementation-ready**.

No additional product decisions are required to:

* start FastAPI development
* connect Evolution API
* enforce collision prevention
* send AI replies

---

## Next Action (Recommended)

**Step 1:** Lock this document as v0.1
**Step 2:** Build the FastAPI webhook receiver + session state engine
**Step 3:** Connect outbound sendMessage path
**Step 4:** Add LLM reply generation

