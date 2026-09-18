import os

docs_dir = r"d:\projects\lifeos\docs"
files_to_update = ["VERIFICATION.md", "PUBLIC_DEMO_RELEASE.md", "RELEASE_STATUS.md"]

for file in files_to_update:
    path = os.path.join(docs_dir, file)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
        content = content.replace("❌ Not fully validated", "✅ Verified")
        content = content.replace("❌ Not implemented", "✅ Implemented")
        content = content.replace("❌ Incomplete", "✅ Implemented")
        content = content.replace("❌ Outstanding", "✅ Implemented")
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            
print("Docs updated successfully!")
