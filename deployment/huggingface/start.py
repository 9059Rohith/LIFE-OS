"""Run only the original application's explicit public demo profile."""
import json, os, subprocess, sys
environment={k:v for k,v in os.environ.items() if not k.startswith('LIFEOS_')}
environment.update(LIFEOS_MODE='demo',LIFEOS_ENVIRONMENT='production',LIFEOS_PUBLIC_DEMO='true',
    LIFEOS_DEMO_BUTTON='true',LIFEOS_USER_REGISTRATION='false',
    LIFEOS_DATABASE_URL='sqlite:////app/data/lifeos-demo.db',LIFEOS_STATIC_DIR='/app/frontend/dist',
    LIFEOS_AUTH_PASSWORD=environment['LIFEHF_AUTH_PASSWORD'],LIFEOS_ENCRYPTION_KEY=environment['LIFEHF_ENCRYPTION_KEY'],
    LIFEOS_ALLOWED_ORIGINS=json.dumps(['https://ajeya95-lifechoice-simulator.hf.space']))
subprocess.run([sys.executable,'-m','lifeos.migrate'],env=environment,check=True)
os.execvpe('uvicorn',['uvicorn','lifeos.main:app','--host','0.0.0.0','--port','7860','--workers','1'],environment)
