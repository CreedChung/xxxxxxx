#!/bin/bash

# AI写标书助手 - 构建脚本 (macOS)
echo "================================================"
echo "AI写标书助手 - 构建可执行文件 (macOS)"
echo "================================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查Python环境
echo -e "${BLUE}检查Python环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3未安装或不在PATH中${NC}"
    echo "请安装Python 3.8或更高版本"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✅ Python版本: $PYTHON_VERSION${NC}"

# 检查Node.js环境
echo -e "${BLUE}检查Node.js环境...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js未安装或不在PATH中${NC}"
    echo "请安装Node.js 14或更高版本"
    exit 1
fi

NODE_VERSION=$(node --version)
echo -e "${GREEN}✅ Node.js版本: $NODE_VERSION${NC}"

# 检查npm
echo -e "${BLUE}检查npm...${NC}"
if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm未安装${NC}"
    exit 1
fi

NPM_VERSION=$(npm --version)
echo -e "${GREEN}✅ npm版本: $NPM_VERSION${NC}"

echo -e "${YELLOW}开始构建...${NC}"
echo -e "${YELLOW}注意：构建前将自动清理以下文件和文件夹：${NC}"
echo -e "${YELLOW}  - dist/ (PyInstaller输出目录)${NC}"
echo -e "${YELLOW}  - build/ (PyInstaller构建缓存)${NC}"
echo -e "${YELLOW}  - frontend/build/ (React构建输出)${NC}"
echo -e "${YELLOW}  - backend/static/ (后端静态文件)${NC}"
echo -e "${YELLOW}  - __pycache__/ (Python缓存)${NC}"
echo -e "${YELLOW}  - *.spec (PyInstaller配置文件)${NC}"
echo

# 检查并激活虚拟环境
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo -e "${GREEN}✅ 使用当前虚拟环境: $VIRTUAL_ENV${NC}"
elif [ -d "backend/myenv" ]; then
    echo -e "${GREEN}✅ 激活后端虚拟环境: backend/myenv${NC}"
    cd backend
    source myenv/bin/activate
    echo -e "${GREEN}✅ 虚拟环境已激活: $VIRTUAL_ENV${NC}"
    cd ..
elif [ -d "myenv" ]; then
    echo -e "${GREEN}✅ 激活根目录虚拟环境: myenv${NC}"
    source myenv/bin/activate
    echo -e "${GREEN}✅ 虚拟环境已激活: $VIRTUAL_ENV${NC}"
else
    echo -e "${YELLOW}⚠️  未检测到虚拟环境，使用系统Python${NC}"
fi

# 运行构建脚本
python3 build.py

if [ $? -eq 0 ]; then
    echo
    echo "================================================"
    echo -e "${GREEN}✅ 构建成功！${NC}"
    echo "可执行文件位于: dist/yibiao-simple"
    echo "================================================"
    
    # 设置可执行权限
    if [ -f "dist/yibiao-simple" ]; then
        chmod +x "dist/yibiao-simple"
        echo -e "${GREEN}✅ 已设置可执行权限${NC}"
    fi
    
    echo
    echo "运行方式："
    echo "  ./dist/yibiao-simple"
    echo "  或者"
    echo "  open dist/yibiao-simple"
else
    echo
    echo "================================================"
    echo -e "${RED}❌ 构建失败！请检查上方的错误信息${NC}"
    echo "================================================"
    exit 1
fi