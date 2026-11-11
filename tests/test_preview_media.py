import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
import numpy as np,soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audio_utils import decode_input,export_video,export_video_copy,ffmpeg,probe
from studio_song import replace_interval

class PreviewMedia(unittest.TestCase):
    def test_decode_crops_before_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);rate=44100;t=np.arange(rate*6)/rate
            signal=.1*np.sin(2*np.pi*(220*t+20*t*t));source=root/'source.wav';sf.write(source,np.column_stack([signal,signal]),rate,subtype='FLOAT')
            _,samples,sr=decode_input(source,root/'clip.wav',600,500,2,3)
            selected,_=sf.read(root/'clip.wav',always_2d=True,dtype='float32')
            self.assertEqual(samples,rate*3);self.assertEqual(sr,rate)
            np.testing.assert_allclose(selected[:,0],signal[2*rate:5*rate],atol=1e-7)
    def test_replace_preserves_exterior_and_stereo(self):
        base=np.zeros((1000,2),dtype='float64');base[:,1]=.25
        patch=np.full((400,2),.5);result=replace_interval(base,patch,200,600,20)
        np.testing.assert_array_equal(result[:200],base[:200]);np.testing.assert_array_equal(result[600:],base[600:])
        np.testing.assert_array_equal(result[220:580],patch[20:-20]);self.assertEqual(result[200,1],.25)
    def test_redo_video_keeps_original_compressed_picture_packets(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);rate=44100;t=np.arange(rate*6)/rate
            source=root/'source.wav';sf.write(source,.1*np.sin(2*np.pi*220*t),rate)
            video=root/'source.mp4'
            ffmpeg(['-v','error','-f','lavfi','-i','testsrc2=s=160x90:r=10','-i',source,'-t','6','-c:v','libx264','-c:a','aac',video])
            short=root/'short.wav';sf.write(short,.1*np.sin(2*np.pi*330*t[:rate*3]),rate)
            preview=root/'preview.mp4';export_video(video,short,preview,start_seconds=2)
            self.assertAlmostEqual(float(probe(preview)['format']['duration']),3,delta=.15)
            revised=root/'revised.mp4';export_video_copy(preview,short,revised)
            def hashes(path):
                result=subprocess.run([os.getenv('FFPROBE','ffprobe'),'-v','error','-select_streams','v:0','-show_packets','-show_data_hash','sha256','-of','json',str(path)],capture_output=True,text=True,check=True)
                return [p['data_hash'] for p in json.loads(result.stdout)['packets']]
            self.assertEqual(hashes(preview),hashes(revised))

if __name__=='__main__':unittest.main()
