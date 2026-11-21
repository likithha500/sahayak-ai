import type { VisitDraft } from '../types/visit'
export interface VisitService { save(record:VisitDraft):Promise<VisitDraft> }
export class MockVisitService implements VisitService { async save(record:VisitDraft){ return {...record} } }
export const visitService: VisitService = new MockVisitService()
