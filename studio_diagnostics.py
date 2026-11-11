"""Export structured diagnostics without recordings, prompts, or voice profiles."""
import json,platform,re,shutil,subprocess,time,zipfile
from pathlib import Path
from studio_paths import PRODUCT,ROOT,STATE,read_json

def safe_message(value):
    value=re.sub(r'(?i)(?:[a-z]:[\\/]|/home/|/Users/)[^\n"<>]+','<本地路径>',str(value))
    return re.sub(r'\b(?:hf_|gh[pousr]_)[A-Za-z0-9]{20,}','<已隐藏>',value)[:1000]

def export_report():
    folder=STATE/'diagnostics';folder.mkdir(parents=True,exist_ok=True)
    data={'product':PRODUCT['id'],'version':PRODUCT['version'],'system':platform.system(),
          'system_release':platform.release(),'machine':platform.machine(),'python':platform.python_version(),
          'free_disk_gib':round(shutil.disk_usage(ROOT).free/1024**3,2),
          'last_error':read_json(STATE/'last-error.json',{})}
    if data['last_error']:data['last_error']['message']=safe_message(data['last_error'].get('message',''))
    ready=read_json(ROOT/'.runtime/ready.json',{})
    data['installation_ready']=bool(ready.get('fingerprint'))
    try:
        options={'creationflags':subprocess.CREATE_NO_WINDOW} if platform.system()=='Windows' else {}
        result=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free,driver_version','--format=csv,noheader'],capture_output=True,text=True,timeout=10,**options)
        data['gpu']=result.stdout.strip() if not result.returncode else '无法读取'
    except (OSError,subprocess.TimeoutExpired):data['gpu']='未检测到 nvidia-smi'
    path=folder/('诊断报告-'+time.strftime('%Y%m%d-%H%M%S')+'.zip')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('diagnostics.json',json.dumps(data,ensure_ascii=False,indent=2))
        archive.writestr('说明.txt','本报告仅包含程序版本、系统、显卡、剩余空间和最近一次错误摘要。\n不包含上传录音、歌曲、输入文字、音色收藏或完整运行日志。\n')
    return str(path)
