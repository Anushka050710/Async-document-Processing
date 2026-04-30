# Meeting Notes — Product Planning

**Date:** January 15, 2024  
**Attendees:** Alice (PM), Bob (Backend), Carol (Frontend), Dave (DevOps)

## Agenda

1. Review async processing architecture
2. Discuss progress tracking implementation
3. Plan export feature

## Discussion

### Async Processing
- Agreed to use Celery with Redis as the message broker
- Workers will publish progress events via Redis Pub/Sub
- Frontend will consume events via Server-Sent Events (SSE)

### Progress Tracking
- Each processing stage emits a named event with percentage
- Events stored in PostgreSQL for audit trail
- Latest status cached in Redis for fast polling fallback

### Export Feature
- Support JSON and CSV formats
- Only finalized documents can be exported
- Filename derived from original upload name

## Action Items

- [ ] Bob: Implement Celery task with multi-stage processing
- [ ] Carol: Build SSE consumer in React
- [ ] Dave: Set up Docker Compose with all services
- [ ] Alice: Write user documentation

## Next Meeting

January 22, 2024 at 10:00 AM

---
*Notes taken by Alice*
