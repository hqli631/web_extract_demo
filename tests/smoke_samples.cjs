// Read-only detection smoke test for the project's actual saved samples.
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
const server=spawn(process.env.PYTHON||'python',['-u','-c',"import serve_review as s; v=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler); print(v.server_port,flush=True);v.serve_forever()"],{cwd:root,env:{...process.env,PYTHONPATH:path.join(root,'.deps')}});
let browser;
(async()=>{
  const port=await new Promise((resolve,reject)=>{server.stdout.once('data',x=>resolve(Number(x.toString().trim())));server.once('error',reject)});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const ctx=await browser.newContext();
  await ctx.route('**/*',r=>r.request().url().startsWith(`http://127.0.0.1:${port}/`)?r.continue():r.abort());
  for(const file of fs.readdirSync(path.join(root,'samples')).filter(x=>x.endsWith('.html'))){
    const page=await ctx.newPage();
    await page.addInitScript(()=>addEventListener('message',e=>{if(e.data?.source==='region-review'&&e.data?.type==='regions')window.detected=e.data.regions}));
    await page.goto(`http://127.0.0.1:${port}/snapshot/${encodeURIComponent(file)}`,{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>window.detected,null,{timeout:20000});
    const counts=await page.evaluate(()=>({regions:detected.length,main:detected.filter(r=>r.is_main).length,body:detected.filter(r=>r.predicted_label==='body').length}));
    console.log(file,counts);
    if(!counts.regions||!counts.main)throw Error('No detectable main content: '+file);
    await page.close();
  }
})().catch(e=>{console.error(e);process.exitCode=1}).finally(async()=>{if(browser)await browser.close();server.kill()});
