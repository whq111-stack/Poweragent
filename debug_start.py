import debugpy
import sys

# 启动调试服务器
debugpy.listen(("localhost", 5678))
print("等待调试器连接...")
debugpy.wait_for_client()

# 导入并运行主程序
sys.argv = ["main.py", "--debug", "--debug-input", "分析电网布局|quit"]
import main
