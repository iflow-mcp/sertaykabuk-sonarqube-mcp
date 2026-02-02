#!/usr/bin/env python3
"""简单的MCP服务测试脚本"""
import asyncio
import json
import sys
import os

# 添加项目路径
sys.path.insert(0, '/app/auto-mcp-upload/data/2727/src')

async def test_mcp_server():
    """测试MCP服务器"""
    # 设置环境变量
    os.environ['SONARQUBE_BASE_URL'] = 'https://sonarqube.example.com'
    os.environ['SONARQUBE_TOKEN'] = 'test_token_123456'

    # 启动MCP服务器进程
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        '-m',
        'src.main',
        '--transport',
        'stdio',
        cwd='/app/auto-mcp-upload/data/2727',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # 等待服务器启动
    await asyncio.sleep(2)

    # 发送初始化请求
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }

    # 发送请求
    process.stdin.write((json.dumps(init_request) + '\n').encode())
    await process.stdin.drain()

    # 读取响应
    response_line = await asyncio.wait_for(process.stdout.readline(), timeout=10)
    if not response_line:
        print("❌ 没有收到响应")
        return False

    try:
        response = json.loads(response_line.decode().strip())
        print(f"✅ 收到初始化响应: {response.get('result', {}).get('serverInfo', {}).get('name', 'Unknown')}")
    except json.JSONDecodeError:
        print(f"❌ 无法解析响应: {response_line.decode()}")
        return False

    # 发送 initialized 通知
    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }
    process.stdin.write((json.dumps(initialized_notification) + '\n').encode())
    await process.stdin.drain()

    # 发送 list_tools 请求
    list_tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list"
    }

    process.stdin.write((json.dumps(list_tools_request) + '\n').encode())
    await process.stdin.drain()

    # 读取工具列表响应
    tools_response_line = await asyncio.wait_for(process.stdout.readline(), timeout=10)
    if not tools_response_line:
        print("❌ 没有收到工具列表响应")
        return False

    try:
        tools_response = json.loads(tools_response_line.decode().strip())
        tools = tools_response.get('result', {}).get('tools', [])
        print(f"✅ 发现 {len(tools)} 个工具:")
        for tool in tools:
            print(f"  - {tool.get('name')}: {tool.get('description', '')}")
        
        return len(tools) > 0
    except json.JSONDecodeError:
        print(f"❌ 无法解析工具列表响应: {tools_response_line.decode()}")
        return False
    finally:
        # 关闭进程
        process.terminate()
        await process.wait()

if __name__ == "__main__":
    try:
        success = asyncio.run(test_mcp_server())
        if success:
            print("\n✅ 本地测试成功！")
            sys.exit(0)
        else:
            print("\n❌ 本地测试失败！")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)