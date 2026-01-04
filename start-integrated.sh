#!/bin/bash

# AI写标书助手 - 单端口集成启动 (macOS)
echo "==============================================="
echo "     AI写标书助手 - 单端口集成启动 (macOS)"
echo "==============================================="
echo

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查前端构建文件
echo -e "${BLUE}检查前端构建文件...${NC}"
if [ ! -f "backend/static/index.html" ]; then
    echo -e "${YELLOW}❌ 前端构建文件不存在，正在构建...${NC}"
    echo
    
    # 检查前端目录
    if [ ! -d "frontend" ]; then
        echo -e "${RED}❌ 前端目录不存在${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}[1/2] 构建前端...${NC}"
    cd frontend
    
    # 检查Node.js和npm
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js未安装${NC}"
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}❌ npm未安装${NC}"
        exit 1
    fi
    
    # 安装依赖
    echo "安装前端依赖..."
    if ! npm install; then
        echo -e "${RED}❌ 前端依赖安装失败${NC}"
        exit 1
    fi
    
    # 构建前端
    echo "构建前端..."
    if ! npm run build; then
        echo -e "${RED}❌ 前端构建失败${NC}"
        exit 1
    fi
    
    cd ..
    
    echo -e "${BLUE}[2/2] 复制构建文件...${NC}"
    # 使用Python复制构建文件
    python3 -c "
import shutil
import os
try:
    if os.path.exists('backend/static'):
        shutil.rmtree('backend/static')
    shutil.copytree('frontend/build', 'backend/static')
    print('✅ 构建文件复制完成')
except Exception as e:
    print(f'❌ 复制失败: {e}')
    exit(1)
"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 构建完成${NC}"
        echo
    else
        echo -e "${RED}❌ 构建文件复制失败${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ 前端构建文件已存在${NC}"
    echo
fi

echo -e "${BLUE}🚀 启动集成服务...${NC}"
echo -e "${BLUE}📡 服务地址: http://localhost:8000${NC}"
echo -e "${BLUE}📚 API文档: http://localhost:8000/docs${NC}"
echo
echo -e "${GREEN}✨ 前后端已集成，无CORS问题！${NC}"
echo "==============================================="
echo

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3未安装${NC}"
    exit 1
fi

# 切换到backend目录并启动服务
cd backend

# 检查并激活虚拟环境
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo -e "${GREEN}✅ 使用虚拟环境: $VIRTUAL_ENV${NC}"
elif [ -d "myenv" ]; then
    echo -e "${GREEN}✅ 激活后端虚拟环境: myenv${NC}"
    source myenv/bin/activate
    echo -e "${GREEN}✅ 虚拟环境已激活: $VIRTUAL_ENV${NC}"
else
    echo -e "${YELLOW}⚠️  未检测到虚拟环境，使用系统Python${NC}"
    echo -e "${YELLOW}建议安装依赖: pip install -r requirements.txt${NC}"
fi

# 启动服务
echo -e "${BLUE}正在启动服务...${NC}"
python3 run.py

echo
echo -e "${BLUE}👋 服务已关闭${NC}"