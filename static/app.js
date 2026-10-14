const form=document.querySelector('#analysis-form');
const fileInput=document.querySelector('#video');
const fileLabel=document.querySelector('#file-label');
const dropzone=document.querySelector('#dropzone');
const previewVideo=document.querySelector('#preview-video');
const canvas=document.querySelector('#preview-canvas');
const context=canvas.getContext('2d');
const cornersInput=document.querySelector('#road-corners');
const cornerStatus=document.querySelector('#corner-status');
const corners=[];
const laneCount=document.querySelector('#lane-count');
const roadWidth=document.querySelector('#road-width');
let videoUrl=null;
let frameReady=false;

function drawFrame(){
  if(!frameReady)return;
  context.drawImage(previewVideo,0,0,canvas.width,canvas.height);
  if(corners.length>1){context.beginPath();corners.forEach((point,index)=>{const x=point[0]*canvas.width,y=point[1]*canvas.height;index?context.lineTo(x,y):context.moveTo(x,y)});if(corners.length===4)context.closePath();context.strokeStyle='#caff3f';context.lineWidth=Math.max(3,canvas.width/500);context.stroke()}
  corners.forEach((point,index)=>{const x=point[0]*canvas.width,y=point[1]*canvas.height;context.beginPath();context.arc(x,y,Math.max(7,canvas.width/90),0,Math.PI*2);context.fillStyle='#caff3f';context.fill();context.fillStyle='#10221e';context.font=`bold ${Math.max(12,canvas.width/50)}px sans-serif`;context.textAlign='center';context.textBaseline='middle';context.fillText(String(index+1),x,y)});
}

function updateCorners(){cornersInput.value=JSON.stringify(corners);cornerStatus.textContent=corners.length===4?'Road marked. Confirm the road width and marked length below.':`Select corner ${corners.length+1} of 4 · ${['far left','far right','near right','near left'][corners.length]}`;drawFrame()}

fileInput.addEventListener('change',()=>{
  const file=fileInput.files[0];if(!file)return;
  fileLabel.textContent=file.name;corners.splice(0);updateCorners();frameReady=false;
  if(videoUrl)URL.revokeObjectURL(videoUrl);videoUrl=URL.createObjectURL(file);previewVideo.src=videoUrl;
  previewVideo.addEventListener('loadedmetadata',()=>{canvas.width=previewVideo.videoWidth;canvas.height=previewVideo.videoHeight;previewVideo.currentTime=Math.min(.5,Math.max(0,previewVideo.duration/4))},{once:true});
  previewVideo.addEventListener('seeked',()=>{frameReady=true;canvas.classList.add('ready');drawFrame()},{once:true});
});

canvas.addEventListener('click',event=>{if(!frameReady||corners.length>=4)return;const rect=canvas.getBoundingClientRect();corners.push([Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))]);updateCorners()});
document.querySelector('#reset-corners').addEventListener('click',()=>{corners.splice(0);updateCorners()});
laneCount.addEventListener('change',()=>{roadWidth.value=(Number(laneCount.value)*3.5).toFixed(1)});
['dragenter','dragover'].forEach(name=>dropzone.addEventListener(name,event=>{event.preventDefault();dropzone.classList.add('drag')}));
['dragleave','drop'].forEach(name=>dropzone.addEventListener(name,event=>{event.preventDefault();dropzone.classList.remove('drag')}));
dropzone.addEventListener('drop',event=>{if(event.dataTransfer.files.length){fileInput.files=event.dataTransfer.files;fileInput.dispatchEvent(new Event('change'))}});

const emptyState=document.querySelector('#empty-state');
const activeState=document.querySelector('#active-state');
const statusCopy=document.querySelector('#status-copy');
const progressLabel=document.querySelector('#progress-label');
const progressValue=document.querySelector('#progress-value');
const progressBar=document.querySelector('#progress-bar');
const submitButton=form.querySelector('button[type=submit]');

function showError(message){statusCopy.textContent=message;statusCopy.classList.add('error');progressLabel.textContent='Analysis failed';submitButton.disabled=false;submitButton.querySelector('span').textContent='Try again'}
async function poll(jobId){try{const response=await fetch(`/api/jobs/${jobId}`);const job=await response.json();if(!response.ok)throw new Error(job.error||'Could not read job status.');progressLabel.textContent=job.message;progressValue.textContent=`${job.progress}%`;progressBar.style.width=`${job.progress}%`;document.querySelector('#events').textContent=job.events;if(job.status==='complete'){statusCopy.textContent='Analysis complete. Your files are ready.';document.querySelector('#vehicles').textContent=job.result.vehicles;document.querySelector('#events').textContent=job.result.events;document.querySelector('#duration').textContent=`${job.result.duration_s.toFixed(1)}s`;document.querySelector('#video-download').href=job.result.video_url;document.querySelector('#report-download').href=job.result.report_url;document.querySelector('#downloads').classList.remove('hidden');submitButton.disabled=false;submitButton.querySelector('span').textContent='Analyze another video';return}if(job.status==='failed'){showError(job.message);return}setTimeout(()=>poll(jobId),900)}catch(error){showError(error.message)}}

form.addEventListener('submit',async event=>{event.preventDefault();if(corners.length!==4){statusCopy.textContent='Mark all four road corners in the preview before analysis.';statusCopy.classList.add('error');return}statusCopy.classList.remove('error');submitButton.disabled=true;submitButton.querySelector('span').textContent='Uploading…';emptyState.classList.add('hidden');activeState.classList.remove('hidden');document.querySelector('#downloads').classList.add('hidden');progressBar.style.width='0%';progressValue.textContent='0%';progressLabel.textContent='Uploading video';statusCopy.textContent='Your video is being prepared for local analysis.';try{const response=await fetch('/api/analyze',{method:'POST',body:new FormData(form)});const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not start analysis.');submitButton.querySelector('span').textContent='Analysis running';poll(data.job_id)}catch(error){showError(error.message)}});

