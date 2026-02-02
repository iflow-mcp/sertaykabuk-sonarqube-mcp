#!/usr/bin/env python3
"""简单测试脚本"""
import asyncio
import sys
sys.path.insert(0, '/app/auto-mcp-upload/data/2727/src')

from src.main import create_mcp

async def test():
    """测试MCP服务器"""
    try:
        # 创建MCP服务器实例
        mcp = create_mcp()
        print("✅ MCP服务器创建成功")
        
        # 获取工具列表
        tools = mcp._mcp_server._tool_manager._tools
        print(f"✅ 发现 {len(tools)} 个工具:")
        for name, tool in tools.items():
            print(f"  - {name}: {tool.description}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)