# useRAGChat Testing Guide

## Manual Testing for scheduleProgressUpdate Fix

### What Was Fixed

1. **Added immediate update mode**: `scheduleProgressUpdate(true)` bypasses `requestAnimationFrame` for real-time updates
2. **Ensured new Map instances**: Every update creates a new Map instance so React detects changes
3. **Added comprehensive logging**: Track every step of the update pipeline
4. **Added state change verification**: Confirm React detects state changes via useEffect

### How to Test

#### 1. Open Browser Console
Open the browser developer tools and go to the Console tab.

#### 2. Trigger Document Summary
- Navigate to a knowledge base with documents
- Ask a question that triggers document summarization
- Watch the console logs

#### 3. Expected Log Sequence

You should see logs in this order:

```
[rag-api] 🔥 doc_summary_chunk event received: {...}
[rag-api] 🔥 Parsed doc_summary_chunk data: {...}
[rag-api] 📞 Calling onDocSummaryChunk callback
[useRAGChat] 📤 onDocSummaryChunk called: {...}
[useRAGChat] 📝 Appending chunk to existing doc: {...}
[useRAGChat] 📊 Current documentProgressRef size: 1
[useRAGChat] 🔄 scheduleProgressUpdate called, immediate: true
[useRAGChat] ⚡ Immediate update mode
[useRAGChat] 🔄 Performing update
[useRAGChat] 🔄 Updating documentProgress state, size: 1
[useRAGChat] 🔍 Map instance check: { isNewInstance: true, ... }
[useRAGChat] ✅ documentProgress state updated
[useRAGChat] 📊 documentProgress state changed: {...}
[useRAGChat] ✅ React successfully detected state change
[DocumentProgress] 🎨 Component rendering: {...}
[DocumentCard] 🎴 Rendering card: {...}
[rag-api] ✅ onDocSummaryChunk callback completed
```

#### 4. Verify Real-Time Display

- **Timing**: Chunks should appear in UI within 100ms (check timestamps in logs)
- **Visual**: You should see text appearing progressively, not all at once
- **Cursor**: A blinking cursor (▌) should appear at the end while processing

#### 5. Check for Issues

**If chunks don't appear:**
- Check if `isNewInstance: true` in logs (Map instance must be new)
- Check if "React successfully detected state change" appears
- Check if DocumentProgress component renders after each chunk

**If updates are slow:**
- Check timestamps between "onDocSummaryChunk called" and "Component rendering"
- Should be < 100ms with immediate mode

**If UI freezes:**
- Check for excessive re-renders in DocumentProgress logs
- May need to add React.memo optimization

### Testing Different Scenarios

1. **Small Document**: Should stream chunks in real-time
2. **Large Document**: Should use recall and still stream
3. **Cached Document**: Should display complete summary immediately
4. **Multiple Documents**: Each should update independently
5. **Session Switch**: Should clear progress when switching sessions

### Performance Verification

Monitor these metrics:
- **Latency**: Time from chunk received to UI update (target: <100ms)
- **Batching**: With immediate mode, each chunk triggers one update
- **Re-renders**: Only affected documents should re-render

### Rollback Plan

If immediate mode causes performance issues:
1. Change `scheduleProgressUpdate(true)` back to `scheduleProgressUpdate()`
2. This will re-enable requestAnimationFrame batching
3. May need to investigate why batching wasn't working originally
