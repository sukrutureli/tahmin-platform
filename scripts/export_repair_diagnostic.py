import json,os,re
from pathlib import Path
from private_reports import Api,DEST
errors=[]
for path in Path('diagnostics').glob('*.log'):
    lines=path.read_text(errors='replace').splitlines()
    exceptions=[line for line in lines if re.match(r'^[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception):',line)]
    errors.append({'file':path.name,'exceptionLines':exceptions[-3:],'traceFrames':[x.strip() for x in lines if x.lstrip().startswith('File "')][-8:]})
report={'sourceRunId':'43529293624','errors':errors}
api=Api(os.environ['PRIVATE_REPORT_TOKEN'])
if api.call(DEST).get('private') is not True:raise ValueError('Private destination required')
head=api.call(DEST+'/git/ref/heads/main')['object']['sha']
tree=api.call(DEST+'/git/commits/'+head)['tree']['sha']
nt=api.call(DEST+'/git/trees','POST',{'base_tree':tree,'tree':[{'path':'deney/current/repair-diagnostics.json','mode':'100644','type':'blob','content':json.dumps(report,ensure_ascii=False)+'\n'}]})['sha']
commit=api.call(DEST+'/git/commits','POST',{'message':'Private primary Control repair diagnostic','tree':nt,'parents':[head]})['sha']
api.call(DEST+'/git/refs/heads/main','PATCH',{'sha':commit,'force':False})
