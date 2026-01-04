#!/bin/bash

# AI写标书助手 - 开发环境启动 (macOS)
echo "==============================================="
echo "     AI写标书助手 - 开发环境启动 (macOS)"
echo "==============================================="
echo

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}检查环境...${NC}"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3未安装"
    exit 1
fi

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 检查虚拟环境 - 按优先级检查
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo -e "${GREEN}✅ 使用当前虚拟环境: $VIRTUAL_ENV${NC}"
elif [ -d "backend/myenv" ]; then
    echo -e "${GREEN}✅ 激活后端虚拟环境: backend/myenv${NC}"
    cd backend
    source myenv/bin/activate
    echo -e "${GREEN}✅ 虚拟环境已激活: $VIRTUAL_ENV${NC}"
elif [ -d "myenv" ]; then
    echo -e "${GREEN}✅ 激活根目录虚拟环境: myenv${NC}"
    source myenv/bin/activate
else
    echo -e "${BLUE}⚠️  未找到虚拟环境，使用系统Python${NC}"
    echo -e "${BLUE}建议安装依赖: pip install -r backend/requirements.txt${NC}"
fi

echo -e "${BLUE}🚀 启动后端服务...${NC}"
echo -e "${BLUE}📡 服务地址: http://localhost:8000${NC}"
echo -e "${BLUE}📚 API文档: http://localhost:8000/docs${NC}"
echo

# 启动后端服务
python3 backend/run.py

echo
echo "👋 服务已关闭"