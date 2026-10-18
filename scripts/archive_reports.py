"""Keep self-contained HTML copies for today/yesterday; retain experiment metrics."""
import argparse,re,shutil,subprocess
from datetime import datetime,timedelta,date
from pathlib import Path
from zoneinfo import ZoneInfo

def days(today=None):
    today=today or datetime.now(ZoneInfo('Europe/Istanbul')).date()
    return {today.isoformat(),(today-timedelta(days=1)).isoformat()}

def html_day(text):
    matches=re.findall(r'<[^>]*class=[\"\'][^\"\']*\bday-title\b[^\"\']*[\"\'][^>]*>\s*(\d{4}-\d{2}-\d{2})\s*<',text)
    return matches[0] if len(set(matches))==1 else None

def archive(root,today=None,history=False):
    root=Path(root);keep=days(today);dest=root/'raporlar';dest.mkdir(exist_ok=True)
    for sport in ['futbol','basketbol']:
        p=root/sport/(sport+'.html')
        text=p.read_text() if p.is_file() else '';d=html_day(text)
        if d in keep:
            out=dest/d;out.mkdir(exist_ok=True);(out/p.name).write_text(text)
        if history:
            for day in sorted(keep):
                if (dest/day/p.name).exists():continue
                rel=sport+'/data/PredictionData-'+day+'.json'
                refs=subprocess.check_output(['git','log','--format=%H','-20','--',rel],cwd=root,text=True).splitlines()
                for ref in refs:
                    v=subprocess.run(['git','show',ref+':'+sport+'/'+sport+'.html'],cwd=root,text=True,capture_output=True)
                    if v.returncode==0 and html_day(v.stdout)==day:
                        (dest/day).mkdir(exist_ok=True);(dest/day/p.name).write_text(v.stdout);break
    for folder in (root/'deney/reports').glob('????-??-??'):
        if folder.name in keep:
            out=dest/folder.name;out.mkdir(exist_ok=True)
            for p in folder.glob('*.html'):
                if p.is_file() and not p.is_symlink():shutil.copyfile(p,out/p.name)
    # Only date-named folders in the dedicated HTML archive are pruned.
    for folder in dest.iterdir():
        if folder.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}',folder.name) and folder.name<min(keep):shutil.rmtree(folder)
    # Historical experiment JSON remains available for the 14-day comparison.
    for folder in (root/'deney/reports').glob('????-??-??'):
        if folder.name<min(keep):
            for p in folder.glob('*.html'):p.unlink()
    return sorted(p.relative_to(root).as_posix() for p in dest.glob('*/*.html'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--history',action='store_true');a=p.parse_args();archive(a.root,history=a.history)
