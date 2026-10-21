"""Load official ai-sage GigaAM-v3 HF weights with the pinned GigaAM implementation."""
import json,urllib.request,hashlib
from pathlib import Path
import torch
from omegaconf import OmegaConf
from gigaam.model import GigaAMASR
def load(download_root,offline=False):
    dest=Path(download_root)/'huggingface-e2e-rnnt';dest.mkdir(parents=True,exist_ok=True)
    if offline:
        provenance=json.loads((dest/'provenance.json').read_text('utf-8'))
        metadata={'sha':provenance['revision'],'siblings':[{'rfilename':name,'lfs':{'sha256':value}} for name,value in provenance['sha256'].items()]}
    else:
        req=urllib.request.Request('https://huggingface.co/api/models/ai-sage/GigaAM-v3/revision/e2e_rnnt?blobs=true',headers={'User-Agent':'ASRComparison'})
        metadata=json.load(urllib.request.urlopen(req,timeout=60))
    revision=metadata['sha']
    checks={}
    for filename in ['config.json','tokenizer.model','pytorch_model.bin']:
        p=dest/filename
        info=next(x for x in metadata['siblings'] if x['rfilename']==filename)
        expected=(info.get('lfs') or {}).get('sha256')
        valid=p.exists() and (not expected or hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==expected)
        if not valid and offline:raise RuntimeError("Local GigaAM assets missing or corrupt; no download attempted")
        if not valid:
            print('Downloading official HF asset '+filename,flush=True)
            url='https://huggingface.co/ai-sage/GigaAM-v3/resolve/'+revision+'/'+filename
            part=p.with_suffix(p.suffix+'.part')
            with urllib.request.urlopen(url,timeout=120) as r,part.open('wb') as f:
                while True:
                    block=r.read(1024*1024)
                    if not block:break
                    f.write(block)
            actual=hashlib.file_digest(part.open('rb'),'sha256').hexdigest()
            if expected and actual!=expected:raise RuntimeError('Model SHA256 mismatch')
            part.replace(p)
        checks[filename]=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
    config=json.loads((dest/'config.json').read_text('utf-8'))['cfg']['model']['cfg']
    targets={'FeatureExtractor':'gigaam.preprocess.FeatureExtractor','ConformerEncoder':'gigaam.encoder.ConformerEncoder','RNNTHead':'gigaam.decoder.RNNTHead','RNNTGreedyDecoding':'gigaam.decoding.RNNTGreedyDecoding'}
    def adapt(obj):
        if isinstance(obj,dict):
            result={}
            for key,value in obj.items():
                if key=='_target_':
                    cls=value.rsplit('.',1)[-1]
                    if cls not in targets:raise ValueError('Unexpected model target '+cls)
                    result[key]=targets[cls]
                else:result[key]=adapt(value)
            return result
        if isinstance(obj,list):return [adapt(v) for v in obj]
        return obj
    config=adapt(config);config['decoding']['model_path']=str(dest/'tokenizer.model')
    config['encoder']['flash_attn']=False;config['model_name']='v3_e2e_rnnt'
    model=GigaAMASR(OmegaConf.create(config))
    state=torch.load(dest/'pytorch_model.bin',map_location='cpu',weights_only=True)
    state={k.removeprefix('model.'):v for k,v in state.items()}
    model.load_state_dict(state,strict=True)
    (dest/'provenance.json').write_text(json.dumps({'repository':'ai-sage/GigaAM-v3','branch':'e2e_rnnt','revision':revision,'sha256':checks,'load_state_dict':'strict passed'},indent=2),'utf-8')
    print('Official HF weights verified and strictly loaded.',flush=True)
    return model.eval().to('cpu')
