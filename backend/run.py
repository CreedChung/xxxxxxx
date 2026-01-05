"""后端服务启动脚本"""
import uvicorn
import os
import subprocess
import shutil
import sys
import multiprocessing
from pathlib import Path

def build_and_copy_frontend():
    """构建前端并复制到后端static目录"""
    print("="*50)
    print("开始构建前端...")
    print("="*50)

    # 获取项目根目录
    backend_dir = Path(__file__).parent
    project_root = backend_dir.parent
    frontend_dir = project_root / "frontend"
    backend_static_dir = backend_dir / "static"

    # 检查前端目录是否存在
    if not frontend_dir.exists():
        print(f"ERROR: 前端目录不存在: {frontend_dir}")
        return False

    try:
        # 进入前端目录并执行构建
        print(f"进入前端目录: {frontend_dir}")
        os.chdir(frontend_dir)

        # 检查是否存在node_modules，如果没有则安装依赖
        node_modules = frontend_dir / "node_modules"
        if not node_modules.exists():
            print("前端依赖不存在，正在安装...")
            result = subprocess.run(['npm', 'install'], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"ERROR: npm install 失败: {result.stderr}")
                return False
            print("✓ 前端依赖安装完成")

        # 执行构建
        print("执行 npm run build...")
        result = subprocess.run(['npm', 'run', 'build'], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR: 前端构建失败 (返回码: {result.returncode})")
            if result.stderr:
                print(f"错误信息: {result.stderr}")
            if result.stdout:
                print(f"输出信息: {result.stdout}")
            return False
        print("✓ 前端构建完成")
        # npm 可能有警告信息，但构建成功了
        if result.stderr and 'npm notice' in result.stderr:
            print("提示: npm 有版本更新通知，但这不影响构建")

        # 确保backend/static目录存在
        print(f"创建/清理后端静态目录: {backend_static_dir}")
        if backend_static_dir.exists():
            shutil.rmtree(backend_static_dir)
        backend_static_dir.mkdir(parents=True, exist_ok=True)

        # 复制构建产物到后端static目录
        frontend_build_dir = frontend_dir / "build"
        if not frontend_build_dir.exists():
            print(f"ERROR: 前端构建产物不存在: {frontend_build_dir}")
            return False

        print(f"复制前端构建产物到: {backend_static_dir}")
        for item in frontend_build_dir.iterdir():
            src = item
            dst = backend_static_dir / item.name
            if item.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        print("✓ 前端构建产物复制完成")
        print("="*50)
        print("前端构建和部署成功！")
        print("="*50)
        return True

    except Exception as e:
        print(f"ERROR: 前端构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 切换回backend目录
        os.chdir(backend_dir)

if __name__ == "__main__":
    # 确保在正确的目录中运行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # 首先构建前端
    print("\n准备前端资源...")
    if not build_and_copy_frontend():
        print("\nWARNING: 前端构建失败，服务器将启动但前端可能无法正常访问")
        # 检查是否在交互式环境中运行
        try:
            input("按回车键继续启动服务器...")
        except EOFError:
            # 非交互式环境（如脚本、CI等），自动继续
            print("检测到非交互式环境，自动启动服务器...")

    print("\n启动后端服务...")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,  # 多进程模式下不支持reload
        log_level="info",
        workers=multiprocessing.cpu_count() * 2  # CPU核心数的2倍，最大化并发能力
    )