path = r'C:\Users\Win10\Desktop\noah_cloud\app.py'

old = "    app.run(debug=True, port=5000, host='0.0.0.0')"
new = "    app.run(debug=True, port=5000, host='0.0.0.0', use_reloader=False)"

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK - use_reloader=False aplicado")
else:
    print("ERROR - no matcheo app.run")
