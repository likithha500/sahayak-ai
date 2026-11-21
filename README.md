# SAHAYAK AI

SAHAYAK AI is a trilingual frontend prototype for ASHA workers to review and record synthetic healthcare visits. It uses Next.js App Router, React, TypeScript, and Tailwind CSS.

## Requirements and setup

- Node.js 20.9 or newer (the project is verified with Node.js 24).
- pnpm 12 (the package manager declared by this repository).
- No environment variables, external services, database, or API keys are required for the demo.

Install dependencies and start the local development server:

```bash
pnpm install
pnpm dev
```

Open the local URL printed by Next.js. To check TypeScript and create a production build:

```bash
pnpm exec tsc --noEmit
pnpm build
```

Microphone recording requires browser permission and a secure context (localhost or HTTPS). If permission is denied or the browser does not support `MediaRecorder`, the app displays an error and the demo scenarios remain available. Audio captured in the recorder is played back locally and is not uploaded or persisted across refreshes.

## Demo workflow

1. Use the Home, Beneficiaries, Follow-ups, Visit history, and Profile navigation to explore the prototype. Choose a beneficiary and start a visit.
2. On the voice screen, optionally record local audio, pause/resume, stop, and play it back. Recording does not create a transcript. Choose any sample scenario to populate synthetic visit details.
3. Review the structured visit fields. For routine visits, missing weight or next-visit date is called out and prevents confirmation/save. An urgent danger-sign referral can be saved without those fields so the referral is not blocked by missing routine details.
4. On the review screen, edit details manually or use the voice-correction simulation: choose exactly one field, enter its corrected value, and apply it. The read-back text reflects the updated values. The simulation does not use speech recognition or a real language model.
5. Explicitly check the confirmation box before saving. The saved visit appears in history and contributes a follow-up row. The two danger scenarios retain their danger flags and urgent referral status.

All beneficiary profiles, scenario transcripts, and seeded history are synthetic. This is not a clinical record system and must not be used for diagnosis or care decisions. The two safety examples are limited to bleeding during pregnancy and high fever in a newborn; they are demonstration alerts, not comprehensive clinical triage.

## Local data and privacy

New demo visits are stored in this browser's `localStorage` under `sahayak-demo-visits-v1`. They survive refreshes in the same browser profile but are not shared across devices or browsers. Clearing site data removes them. The local recorder's audio remains in memory for the current page session only. Do not enter real patient information.

## Architecture and future integration points

- `app/` — App Router shell, page entry point, and global styling.
- `src/components/sahayak-app.tsx` — frontend navigation and visit workflow screens.
- `src/components/voice-recorder.tsx` — browser-local audio capture and playback; no speech-to-text.
- `src/data/mock.ts` and `src/data/translations.ts` — synthetic demo content and Kannada, Hindi, and English UI copy.
- `src/hooks/use-sahayak-app.ts` — workflow state, field corrections, safety assessment, confirmation, and save orchestration.
- `src/services/mock.service.ts` — local demo-visit persistence boundary.
- `src/services/extraction.service.ts` and `src/services/safety.service.ts` — deterministic demo extraction and the two explicitly scoped danger-sign patterns.
- `src/types/` — visit and speech-event contracts.

Future speech-to-text, text-to-speech, or backend integration should be added behind the service boundaries and explicitly wired to the workflow. A production backend would need appropriate authentication, patient-data protections, consent and retention policies, and clinically reviewed safety logic. No such services or AI functionality are currently connected.
