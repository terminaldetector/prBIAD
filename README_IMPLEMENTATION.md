# AI Edge Gallery - Unified Chat Architecture (v2.0)

## 📋 Implementation Plan

This document describes the complete refactoring from multi-screen tabbed interface to a unified single-screen chat experience with switchable modes.

### 🎯 Project Goals

1. **Single Chat Screen**: Unified interface for all interactions
2. **Dynamic Modes**: Reasoning, Actions, and RAG modes can be toggled independently
3. **Native Actions**: No WebView - all actions through MCP and native APIs
4. **RAG Integration**: Real-time document indexing and semantic search
5. **Optimized for Mobile**: Target performance on Redmi Turbo 3 (8GB RAM)

---

## 🏗️ Architecture Overview

### Core Components

```
┌────────────────────────────────────────────┐
│         ChatFragment (UI)            │
├────────────────────────────────────────────┤
│  - Mode toggles (Reasoning/Actions/RAG)
│  - Message display (RecyclerView)
│  - Chat input
└────────────────────┬────────────────────────┘
               ↓
┌────────────────────────────────────────────┐
│      ChatViewModel (State)           │
├────────────────────────────────────────────┤
│  - Message history
│  - Mode state management
│  - Loading states
└──��─────────────────┬────────────────────────┘
               ↓
    ┌────────────┴──────────────┐
    ↓                     ↓
┌──────────────────────┐  ┌─────────────────────┐
│DynamicPromptBuilder│ │SkillManager       │
├──────────────────────┤  ├─────────────────────┤
│- buildSystemPrompt │ │- Available skills │
│  (modes dependent) │ │- Skill execution  │
└──────────────────────┘  └────────┬───────────┘
                                 ↓
                     ┌──────────────────────────────────┐
                     │      Skills            │
                     ├──────────────────────────────────┤
                     │- NativeActionSkill    │
                     │- WebScraperSkill      │
                     │- RAGSkill             │
                     └──────────────────────────────────┘
                                 ↓
                     ┌──────────────────────────────────┐
                     │ External Services     │
                     ├──────────────────────────────────┤
                     │- MCPClient (Actions)  │
                     │- RagEngine (Search)   │
                     │- Jsoup (Scraping)     │
                     └──────────────────────────────────┘
```

---

## 📦 File Structure

```
app/src/main/
├── kotlin/com/google/ai/edge/gallery/
│   ├── ui/
│   │   ├── chat/
│   │   │   └── ChatFragment.kt          # Main UI screen
│   │   ├── adapter/
│   │   │   └── ChatMessageAdapter.kt    # RecyclerView adapter
│   ├── viewmodel/
│   │   └── ChatViewModel.kt             # ViewModel with state management
│   ├── domain/
│   │   ├── DynamicPromptBuilder.kt      # System prompt construction
│   │   ├── SkillManager.kt              # Skill lifecycle management
│   │   ├── skills/
│   │   │   ├── Skill.kt                 # Skill interface
│   │   │   ├── NativeActionSkill.kt     # Device actions (SMS, Alarm, etc)
│   │   │   ├── WebScraperSkill.kt       # HTML parsing with Jsoup
│   │   │   └── RAGSkill.kt              # RAG search
│   │   ├── rag/
│   │   │   └── RagEngine.kt             # RAG indexing and search
│   │   └── mcp/
│   │       └── MCPClient.kt             # MCP protocol client
│   └── data/
│       ├── ChatMessage.kt               # Data model
│       └── SkillResult.kt               # Result wrapper
└── res/
    └── layout/
        ├── fragment_chat.xml            # Main UI layout
        └── item_chat_message.xml        # Message item layout
```

---

## 🔄 Implementation Phases

### Phase 1: ✅ Architectural Refactoring (COMPLETE)
- [x] Remove TabLayout and Navigation Graph complexity
- [x] Create unified ChatFragment as single screen
- [x] Implement mode toggle system (Reasoning/Actions/RAG)
- [x] Create DynamicPromptBuilder for mode-dependent prompts
- [x] Update SkillManager to support dynamic skill loading

### Phase 2: 🔧 Native Actions (WebView → MCP)
- [ ] Remove WebView dependency from build.gradle
- [ ] Implement MCPClient for action execution
- [ ] Create NativeActionSkill with methods:
  - [ ] send_message (SMS)
  - [ ] set_alarm (AlarmManager)
  - [ ] open_app (Intent)
  - [ ] take_photo (Camera API)
  - [ ] search_web (HTTP requests)
- [ ] Create WebScraperSkill using Jsoup
- [ ] Remove JsSkillLoader

### Phase 3: 📚 RAG Integration
- [ ] Integrate AI Edge RAG SDK
- [ ] Implement RagEngine with:
  - [ ] Document upload and chunking
  - [ ] Embedding generation (Gemma 300M)
  - [ ] Semantic search with similarity scoring
  - [ ] Chunk indexing
- [ ] Create RAG UI components:
  - [ ] Document picker
  - [ ] Loaded documents list
  - [ ] Chunk counter
- [ ] Implement source references in chat messages

### Phase 4: 🧪 Testing & Optimization
- [ ] Profile memory usage on Redmi Turbo 3
- [ ] Benchmark inference time (RAG search < 300ms target)
- [ ] Implement quantization (INT8) for models
- [ ] Enable zRAM for virtual memory
- [ ] Build release APK with ProGuard obfuscation
- [ ] Performance testing on actual device

---

## 🚀 Getting Started

### Prerequisites
- Android Studio (latest)
- Kotlin 1.9+
- Gradle 8.0+
- Min SDK: 26 (Android 8.0)
- Target SDK: 34 (Android 14)

### Build & Run

```bash
# Clone repository
git clone https://github.com/hren4073-cpu/gitShlak.git
cd gitShlak

# Create feature branch
git checkout feature/unified-chat-with-rag

# Build project
./gradlew build

# Run on device
./gradlew installDebug
```

### Configuration

Update `build.gradle.kts` with your configurations:
- `minSdk`: Minimum Android version
- `targetSdk`: Target Android version
- Dependencies versions

---

## 📝 Mode Usage Guide

### 🧠 Reasoning Mode
When enabled:
- AI shows thinking process in `<thinking>...</thinking>` tags
- Breaks down complex problems into steps
- Takes longer but provides more accurate responses

### ⚡ Actions Mode
When enabled:
- Grants access to native device actions
- Available: SMS, alarms, app launching, camera, web search
- All actions through MCP protocol (no WebView)
- Requires user confirmation for sensitive actions

### 📚 RAG Mode
When enabled:
- AI searches uploaded documents for context
- Shows source references [Source: document_name]
- Combines RAG results with general knowledge
- Real-time indexing as documents are added

---

## 🔐 Security Considerations

1. **Permissions**: Implement fine-grained permission requests
2. **API Keys**: Store in secure KeyStore, not hardcoded
3. **MCP Communication**: Use encrypted channels
4. **User Confirmations**: Always confirm sensitive actions
5. **Data Privacy**: RAG documents stored locally, never sent to servers

---

## 📊 Performance Targets

- **RAG Search**: < 300ms for similarity search
- **Memory**: Total usage < 8GB (Redmi Turbo 3)
- **Inference**: < 2 seconds per response
- **App Startup**: < 3 seconds
- **Battery**: Minimal impact with optimized inference

---

## 🐛 Known Limitations (Phase 1)

1. **Embedding Generation**: Not yet implemented (Phase 3)
2. **RAG Search**: Placeholder only (Phase 3)
3. **MCP Integration**: Skeleton implementation (Phase 2)
4. **Model Inference**: Integration pending (to be added)
5. **UI Polish**: Basic layouts, needs refinement

---

## 📚 Dependencies

### Core
- `androidx.core:core-ktx:1.12.0`
- `androidx.appcompat:appcompat:1.6.1`
- `androidx.lifecycle:lifecycle-*:2.6.2`

### UI
- `com.google.android.material:material:1.10.0`
- `androidx.recyclerview:recyclerview:1.3.2`

### Networking
- `com.squareup.okhttp3:okhttp:4.11.0`
- `com.google.code.gson:gson:2.10.1`

### AI/ML
- `com.google.ai.edge:rag:1.0.0`
- `com.google.ai.edge:inference:1.0.0`
- `org.tensorflow:tensorflow-lite:2.14.0`

### Utilities
- `org.jsoup:jsoup:1.16.1` (HTML parsing)
- `androidx.room:room-*:2.6.1` (Database)
- `androidx.datastore:datastore-preferences:1.0.0` (Preferences)

---

## 🤝 Contributing

Follow the architecture outlined in this document. Each feature should:
1. Implement the Skill interface or extend existing classes
2. Add error handling with Result wrapper
3. Support coroutines for async operations
4. Include unit tests

---

## 📄 License

TBD

---

## 📞 Support

For issues or questions, please open a GitHub issue in the repository.
