export interface SpeechService {
  connect(onPartial: (text: string) => void, onFinal: (text: string) => void): Promise<void>
  sendAudioChunk(chunk: Blob): Promise<void>
  disconnect(): Promise<void>
}

export type SpeechServiceFactory = () => SpeechService

export const createSpeechService = (factory: SpeechServiceFactory): SpeechService => factory()
