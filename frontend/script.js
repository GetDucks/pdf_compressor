const $=id=>document.getElementById(id);
let url;
const fmt=n=>{const u=["B","KB","MB","GB"];let i=0;while(n>=1000&&i<u.length-1){n/=1000;i++}return `${n.toFixed(i?2:0)} ${u[i]}`};
$("file").onchange=()=>{const f=$("file").files[0];$("fileText").textContent=f?`${f.name} · ${fmt(f.size)}`:"Maximum upload: 100 MB"};
$("form").onsubmit=async e=>{
 e.preventDefault();const f=$("file").files[0];if(!f)return fail("Select a PDF first.");
 const target=+$("target").value/($("unit").value==="kb"?1000:1);
 const data=new FormData();data.append("file",f);data.append("target_mb",target);data.append("minimum_dpi",$("mode").value);data.append("grayscale",$("gray").checked);
 $("working").classList.remove("hidden");$("result").classList.add("hidden");$("error").classList.add("hidden");$("submit").disabled=true;
 try{
  const base=window.APP_CONFIG.API_BASE_URL.replace(/\/$/,"");
  const r=await fetch(`${base}/compress`,{method:"POST",body:data});
  if(!r.ok){let j=await r.json().catch(()=>({}));throw Error(j.detail||"Compression failed.")}
  const b=await r.blob(),o=+(r.headers.get("X-Original-Size-Bytes")||f.size),c=+(r.headers.get("X-Compressed-Size-Bytes")||b.size);
  if(url)URL.revokeObjectURL(url);url=URL.createObjectURL(b);
  $("original").textContent=fmt(o);$("compressed").textContent=fmt(c);$("reduction").textContent=`${Math.max(0,(1-c/o)*100).toFixed(1)}%`;
  const reached=r.headers.get("X-Target-Reached")==="true",dpi=r.headers.get("X-Selected-DPI");
  $("message").textContent=reached?`Target reached at about ${dpi} DPI.`:"Target was not reachable at the selected quality floor; the smallest acceptable result was returned.";
  $("download").href=url;$("download").download=f.name.replace(/\.pdf$/i,"")+"-compressed.pdf";$("result").classList.remove("hidden");
 }catch(err){fail(err.message)}finally{$("working").classList.add("hidden");$("submit").disabled=false}
};
function fail(m){$("error").textContent=m;$("error").classList.remove("hidden")}