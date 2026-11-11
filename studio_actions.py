"""Small CPU-only media actions in the singing environment."""
from pathlib import Path
import argparse,json

def main():
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('directory');parser.add_argument('--start',type=float,default=0);parser.add_argument('--seconds',type=float,default=20)
    parser.add_argument('--prepared',action='store_true')
    args=parser.parse_args();folder=Path(args.directory);folder.mkdir(parents=True,exist_ok=True)
    from reference_audio import prepare_reference
    import numpy as np,soundfile as sf
    if args.prepared:
        from reference_audio import use_prepared
        reference,info=use_prepared(args.source,folder)
        samples,sample_rate=sf.read(reference,dtype='float32')
        sf.write(reference,samples,sample_rate,subtype='PCM_24')
    else:reference,info=prepare_reference(args.source,folder,args.start,args.seconds)
    wave,rate=sf.read(reference,dtype='float32')
    info.update(path=str(reference),rms=float(np.sqrt(np.mean(wave.astype('float64')**2))),peak=float(np.max(np.abs(wave))))
    print(json.dumps(info,ensure_ascii=True))

if __name__=='__main__':main()
