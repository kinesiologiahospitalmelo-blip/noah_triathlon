path = r'C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\App.js'

old = """import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, BarChart, Bar
} from 'recharts'"""

new = """import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, BarChart, Bar,
  ScatterChart, Scatter, ReferenceLine, AreaChart, Area
} from 'recharts'"""

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Bug 1 resuelto — imports de recharts actualizados")
else:
    print("❌ No matcheó el texto exacto — verificar manualmente")
