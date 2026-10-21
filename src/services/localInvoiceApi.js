// Local in-memory service. Records reset when the page reloads.
import { workspaceInvoices } from '../data/workspaceRecords'
let db=structuredClone(workspaceInvoices)
const files=new Map()
const find=id=>{const i=db.find(x=>x.id===id);if(!i)throw new Error('Invoice not found.');return i}
export const localApi={
  health:async()=>({ok:true,mode:'local'}),
  list:async()=>structuredClone(db),
  get:async id=>structuredClone(find(id)),
  getFile:id=>files.get(id)||null,
  upload:async file=>{const id='upload-'+Date.now();files.set(id,file)
    db.unshift({id,invoiceNumber:null,vendor:{name:'',address:'',taxId:''},customer:{name:'',address:'',taxId:''},invoiceDate:null,dueDate:null,currency:'INR',paymentTerms:null,subtotal:null,taxAmount:null,discount:null,totalAmount:null,lineItems:[],processingStatus:'uploaded',reviewStatus:'pending',confidence:{},validationWarnings:[{message:'Automated extraction is not connected in the current workspace. Review and enter invoice values manually.',severity:'info'}],createdAt:new Date().toISOString(),updatedAt:new Date().toISOString(),originalFileUrl:null})
    return structuredClone(db[0])},
  save:async(id,data)=>{const i=db.findIndex(x=>x.id===id);if(i<0)throw new Error('Invoice not found.');db[i]={...db[i],...data,updatedAt:new Date().toISOString()};return structuredClone(db[i])},
  setReview:async(id,s)=>{const i=find(id);i.reviewStatus=s;i.updatedAt=new Date().toISOString();return structuredClone(i)},
}
