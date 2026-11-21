export interface TextToSpeechService { play(text:string,language:'kn'|'hi'|'en'):Promise<void>; stop():void }
export class DemoTextToSpeechService implements TextToSpeechService { async play(_text:string,_language:'kn'|'hi'|'en'){return} stop(){} }
export const textToSpeechService:TextToSpeechService=new DemoTextToSpeechService()
