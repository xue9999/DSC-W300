"""Selected ELF routines only, static decoding; uses existing pinned ELF helper."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'g3-usb-descriptor'))
from inspect_usb import Elf
selected={
 'evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/PExtSenser.so':[
  'xs_senser_on','xs_senser_ready','_ZN6Senser2OnEv','_ZN6Senser5ReadyERNS_14StatusCallbackE',
  '_ZN6Senser9Extension20active_event_handlerE15__SENIF_EVENT_TPhji',
  '_ZN6Senser9Extension12workerThreadEPv','_ZN10CoreModule9nin_startER13NinCooperator'],
 'evidence/extracted_g3/archives_unpacked/bin/bin/sen':['main'],
 'evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/usbExt.so':['xs_reqStart'],
 'evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/USBGMsc.so':['xs_USBGMsc_extCmd_register'],
}
if '--extra' in sys.argv:
 selected={
  'evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/PExtSenser.so':[
   '_ZNK6Senser9Extension12getProductIdEv','_ZN6Senser9Extension10onCompleteEi',
   '_ZN6Senser9Extension13senif_destroyEv','_ZN6Senser9Extension10senif_initEv',
   '_ZN10CoreModule4openEv','_ZN6Senser9Extension14getReceiveFuncEv','_ZN6Senser9Extension11getSendFuncEv'],
  'evidence/extracted_g3/archives_unpacked/bin/bin/sen':['_ZN17PowerEventHandler9onPowerOnEv'],
  'evidence/extracted_g3/archives_unpacked/lib/lib/libsencore.so':['shimashima'],
 }
for relative,names in selected.items():
 e=Elf(relative)
 lines=['Static G3 code only. Symbol-size decoding may include trailing literal pools; those words are not claimed executed.',relative,e.sha]
 lines.extend(e.decode(n) for n in names)
 target=HERE/(Path(relative).name+('-extra' if '--extra' in sys.argv else '')+'.asm.txt')
 target.write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
 print(target.name,len(names))
