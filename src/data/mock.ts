import type { VisitRecord } from '@/src/types/visit'

export interface Beneficiary { id:string; name:string; category:'Pregnant'|'Newborn'; detail:string; lastVisit:string; nextVisit:string; initial:string; color:string }
export const beneficiaries: Beneficiary[] = [
{id:'AS-102',name:'Meena Kumari',category:'Pregnant',detail:'28 weeks',lastVisit:'18 Nov 2026',nextVisit:'24 Nov',initial:'ಮ',color:'rose'},
{id:'AS-205',name:'Baby of Kavya',category:'Newborn',detail:'12 days',lastVisit:'16 Nov 2026',nextVisit:'22 Nov',initial:'ಕ',color:'blue'},
{id:'AS-118',name:'Sujatha R.',category:'Pregnant',detail:'32 weeks',lastVisit:'12 Nov 2026',nextVisit:'26 Nov',initial:'ಸು',color:'gold'},
{id:'AS-211',name:'Baby of Rekha',category:'Newborn',detail:'3 months',lastVisit:'10 Nov 2026',nextVisit:'26 Nov',initial:'ರ',color:'mint'},
{id:'AS-136',name:'Anitha N.',category:'Pregnant',detail:'24 weeks',lastVisit:'14 Nov 2026',nextVisit:'28 Nov',initial:'ಅ',color:'lilac'},
{id:'AS-223',name:'Baby of Farzana',category:'Newborn',detail:'6 weeks',lastVisit:'17 Nov 2026',nextVisit:'29 Nov',initial:'ಫ',color:'peach'},
]
export interface Scenario { id:string; title:string; description:string; transcript:string; type:string; weight?:string; vaccines?:string; date?:string; danger:boolean; lang:string; alert?:Partial<Record<'kn'|'hi'|'en',string>> }
export const scenarios: Scenario[] = [
{id:'pregnancy',title:'Normal pregnancy visit',description:'ANC check-up · mixed Kannada-English',transcript:'ಇವತ್ತು beneficiary 102 ಮನೆಗೆ ಹೋಗಿದ್ದೆ. ANC checkup ಆಗಿದೆ. TT injection due ಇದೆ. Next visit Monday.',type:'Pregnancy visit',vaccines:'TT injection',date:'2026-11-23',danger:false,lang:'kn'},
{id:'newborn',title:'Newborn visit',description:'Baby weight · Hindi-English',transcript:'Beneficiary 205 newborn baby weight 2.8 kilo hai. Next visit tomorrow.',type:'Newborn visit',weight:'2.8',date:'2026-11-21',danger:false,lang:'hi'},
{id:'preg-danger',title:'Pregnancy danger sign',description:'Bleeding during pregnancy',transcript:'Pregnant woman ge bleeding agta ide.',type:'Pregnancy visit',danger:true,lang:'kn',alert:{kn:'ಗರ್ಭಾವಸ್ಥೆಯಲ್ಲಿ ರಕ್ತಸ್ರಾವ ವರದಿಯಾಗಿದೆ.',hi:'गर्भावस्था के दौरान रक्तस्राव की सूचना मिली है।',en:'Bleeding during pregnancy was reported.'}},
{id:'newborn-danger',title:'Newborn danger sign',description:'High fever in a newborn',transcript:'Newborn baby ko high fever hai.',type:'Newborn visit',danger:true,lang:'hi',alert:{kn:'ನವಜಾತ ಶಿಶುವಿನಲ್ಲಿ ಹೆಚ್ಚಿನ ಜ್ವರ ವರದಿಯಾಗಿದೆ.',hi:'नवजात शिशु में तेज़ बुखार की सूचना मिली है।',en:'High fever in a newborn was reported.'}},
{id:'correction',title:'Voice correction',description:'Correct a detail by voice',transcript:'No, weight is 2.8 kilo.',type:'Newborn visit',weight:'',danger:false,lang:'en'},
{id:'missing',title:'Missing information',description:'Clarify details before saving',transcript:'Visited the newborn today. Baby is doing well.',type:'Newborn visit',danger:false,lang:'en'},
{id:'mixed',title:'Mixed-language visit',description:'Kannada + Hindi + English',transcript:'ಇವತ್ತು ಮನೆಗೆ ಭೇಟಿ ಕೊಟ್ಟೆ. Maa ne bola baby ठीक है. Next visit Monday.',type:'Newborn visit',danger:false,lang:'kn'},
]

export interface ScheduledVisit { id:string; time:string; state:'Completed'|'Needs review'|'Upcoming'|'Flagged' }
export const todayVisits: ScheduledVisit[] = [
  { id:'AS-102', time:'09:30 AM', state:'Completed' },
  { id:'AS-205', time:'11:00 AM', state:'Needs review' },
  { id:'AS-118', time:'02:30 PM', state:'Upcoming' },
  { id:'AS-211', time:'03:00 PM', state:'Completed' },
  { id:'AS-136', time:'03:30 PM', state:'Completed' },
  { id:'AS-223', time:'04:00 PM', state:'Completed' },
  { id:'AS-102', time:'04:30 PM', state:'Completed' },
  { id:'AS-205', time:'05:00 PM', state:'Flagged' },
]

export const followUpSchedule = [
  { id:'AS-205', category:'Newborn check', date:'22 Nov 2026', status:'Upcoming' },
  { id:'AS-102', category:'ANC follow-up', date:'24 Nov 2026', status:'Upcoming' },
  { id:'AS-211', category:'Immunisation', date:'26 Nov 2026', status:'Upcoming' },
  { id:'AS-118', category:'Pregnancy visit', date:'18 Nov 2026', status:'Overdue' },
]

export const historyRecords: VisitRecord[] = [
  { id:'V-28401', draftId:'legacy-28401', beneficiaryId:'AS-102', type:'Pregnancy visit', date:'20 Nov 2026', nextDate:'24 Nov 2026', status:'Completed', danger:false, dangerFlags:[], weight:'57.2', vaccines:'', notes:'' },
  { id:'V-28398', draftId:'legacy-28398', beneficiaryId:'AS-205', type:'Newborn visit', date:'19 Nov 2026', nextDate:'22 Nov 2026', status:'Needs review', danger:false, dangerFlags:[], weight:'', vaccines:'', notes:'' },
  { id:'V-28392', draftId:'legacy-28392', beneficiaryId:'AS-118', type:'Pregnancy visit', date:'18 Nov 2026', nextDate:'26 Nov 2026', status:'Flagged', danger:true, dangerFlags:['bleeding-during-pregnancy'], weight:'', vaccines:'', notes:'' },
]
