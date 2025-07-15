#!/usr/bin/env python3
"""
Comprehensive test suite for ESP RainMaker MCP Server.
Tests actual functionality when logged in, gracefully skips when not.
"""

import asyncio
import sys
import inspect
from pathlib import Path

def check_authentication_status():
    """Check if user is logged in to ESP RainMaker."""
    print("🔍 Checking authentication status...")
    try:
        import server

        # Try to create a session - if this works, user is logged in
        session = asyncio.run(asyncio.to_thread(server.ensure_login_session))

        # Try to get username for confirmation
        from rmaker_lib import configmanager as rainmaker_config
        config = rainmaker_config.Config()
        user_name = config.get_user_name()

        print(f"✅ User is logged in as: {user_name}")
        return True, user_name

    except Exception as e:
        print(f"ℹ️  No authentication detected: {type(e).__name__}")
        return False, str(e)

def test_imports():
    """Test that all required modules can be imported."""
    print("🔍 Testing imports...")

    try:
        import server
        print("✅ server module imported successfully")

        from server import mcp
        print("✅ FastMCP instance imported successfully")

        # Test that it's actually a FastMCP instance
        from mcp.server.fastmcp import FastMCP
        assert isinstance(mcp, FastMCP), "mcp is not a FastMCP instance"
        print("✅ mcp is valid FastMCP instance")

        return True
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def test_tool_registration():
    """Test that MCP tools are properly registered."""
    print("\n🔧 Testing tool registration...")

    try:
        import server
        import inspect

        # Find all functions decorated with @mcp.tool()
        tool_functions = []

        # Look for functions that are likely MCP tools by checking if they're async
        # and have the expected pattern
        for name, obj in inspect.getmembers(server):
            if (inspect.iscoroutinefunction(obj) and
                name not in ['ensure_login_session', 'add_nodes_to_group_hierarchically'] and  # exclude helpers
                not name.startswith('_')):  # exclude private functions

                # Check if function signature suggests it's an MCP tool
                sig = inspect.signature(obj)
                params = list(sig.parameters.keys())

                # MCP tools either have no params (like login_instructions)
                # or have 'ctx' as first parameter
                if (len(params) == 0 or  # no parameters (like login_instructions)
                    (params and 'ctx' in params[0])):  # or ctx parameter
                    tool_functions.append(name)

        tool_count = len(tool_functions)
        print(f"✅ Found {tool_count} MCP tool functions: {tool_functions}")

        # Expected core tools (updated list)
        expected_tools = [
            'login_instructions',
            'check_login_status',
            'get_nodes',
            'get_node_status',
            'get_params',
            'set_params',
            'get_node_details',
            'get_schedules',
            'set_schedule',
            'create_group',
            'add_device_to_room',
            'update_group',
            'get_group_details'
        ]

        missing_tools = []
        for tool in expected_tools:
            if tool not in tool_functions:
                missing_tools.append(tool)

        if missing_tools:
            print(f"⚠️  Missing expected tools: {missing_tools}")
        else:
            print("✅ All expected tools are present")

        # Check if we have the expected number of tools (13)
        expected_count = 13
        if tool_count == expected_count:
            print(f"✅ Tool count matches expected ({expected_count})")
        else:
            print(f"⚠️  Tool count mismatch: found {tool_count}, expected {expected_count}")

        return tool_count > 0 and len(missing_tools) == 0

    except Exception as e:
        print(f"❌ Tool registration test failed: {e}")
        return False

def test_async_compatibility():
    """Test that async functions can be called."""
    print("\n⚡ Testing async compatibility...")

    try:
        import server

        # Test async function detection
        async_functions = []
        for name, obj in inspect.getmembers(server):
            if inspect.iscoroutinefunction(obj):
                async_functions.append(name)

        print(f"✅ Found {len(async_functions)} async functions")

        # Test basic asyncio functionality
        async def test_async():
            await asyncio.sleep(0.01)
            return "async_test_passed"

        result = asyncio.run(test_async())
        assert result == "async_test_passed"
        print("✅ Asyncio functionality confirmed")

        return True

    except Exception as e:
        print(f"❌ Async compatibility test failed: {e}")
        return False

def test_login_instructions():
    """Test the login instructions tool (doesn't require actual login)."""
    print("\n📋 Testing login instructions...")

    try:
        import server

        # Test login_instructions function
        result = asyncio.run(server.login_instructions())

        assert isinstance(result, str), "login_instructions should return a string"
        assert len(result) > 0, "login_instructions should return non-empty content"
        assert "ESP RainMaker" in result, "Should mention ESP RainMaker"
        assert "login" in result.lower(), "Should mention login"

        print("✅ login_instructions function works correctly")
        return True

    except Exception as e:
        print(f"❌ Login instructions test failed: {e}")
        return False

def test_tools_with_authentication(user_name):
    """Test actual tool functionality when user is logged in."""
    print(f"\n🔐 Testing tools with authentication (user: {user_name})...")

    try:
        import server

        class MockContext:
            pass

        mock_ctx = MockContext()
        success_count = 0
        total_tests = 0

        # Test check_login_status
        total_tests += 1
        try:
            result = asyncio.run(server.check_login_status(mock_ctx))
            assert isinstance(result, str)
            assert user_name in result
            print(f"✅ check_login_status: {result}")
            success_count += 1
        except Exception as e:
            print(f"❌ check_login_status failed: {e}")

        # Test get_nodes
        total_tests += 1
        try:
            result = asyncio.run(server.get_nodes(mock_ctx))
            if isinstance(result, list):
                print(f"✅ get_nodes: Found {len(result)} devices")
            else:
                print(f"✅ get_nodes: {result}")
            success_count += 1
        except Exception as e:
            print(f"❌ get_nodes failed: {e}")

        # Test get_node_details (all nodes)
        total_tests += 1
        try:
            result = asyncio.run(server.get_node_details(mock_ctx, None))
            if isinstance(result, dict):
                node_count = len(result)
                print(f"✅ get_node_details: Retrieved details for {node_count} nodes")
            else:
                print(f"✅ get_node_details: {result}")
            success_count += 1
        except Exception as e:
            print(f"❌ get_node_details failed: {e}")

        # Test get_group_details
        total_tests += 1
        try:
            result = asyncio.run(server.get_group_details(mock_ctx, None, False))
            if isinstance(result, dict):
                print(f"✅ get_group_details: Retrieved group information")
            else:
                print(f"✅ get_group_details: {result}")
            success_count += 1
        except Exception as e:
            print(f"❌ get_group_details failed: {e}")

        print(f"✅ Authenticated tool tests: {success_count}/{total_tests} passed")
        return success_count == total_tests

    except Exception as e:
        print(f"❌ Authenticated tool testing failed: {e}")
        return False

def test_tools_without_authentication():
    """Test that tools handle no authentication gracefully."""
    print("\n🔐 Testing tools without authentication (error handling)...")

    try:
        import server

        class MockContext:
            pass

        mock_ctx = MockContext()
        success_count = 0
        total_tests = 0

        # Test that tools return error messages instead of crashing
        tools_to_test = [
            ('get_nodes', lambda: server.get_nodes(mock_ctx)),
            ('get_node_details', lambda: server.get_node_details(mock_ctx, None)),
            ('get_group_details', lambda: server.get_group_details(mock_ctx, None, False)),
        ]

        for tool_name, tool_func in tools_to_test:
            total_tests += 1
            try:
                result = asyncio.run(tool_func())
                if isinstance(result, str) and "Login required" in result:
                    print(f"✅ {tool_name}: Correctly returns auth error")
                    success_count += 1
                else:
                    print(f"⚠️  {tool_name}: Unexpected result: {result}")
            except Exception as e:
                print(f"❌ {tool_name}: Crashed instead of graceful error: {e}")

        print(f"✅ Non-authenticated tool tests: {success_count}/{total_tests} passed")
        return success_count == total_tests

    except Exception as e:
        print(f"❌ Non-authenticated tool testing failed: {e}")
        return False

def test_session_handling(is_authenticated, user_info):
    """Test session handling based on authentication status."""
    if is_authenticated:
        return test_tools_with_authentication(user_info)
    else:
        return test_tools_without_authentication()

def test_helper_functions():
    """Test helper functions and utilities."""
    print("\n🛠️  Testing helper functions...")

    try:
        import server

        # Test that ensure_login_session function exists
        assert hasattr(server, 'ensure_login_session'), "ensure_login_session function should exist"
        print("✅ ensure_login_session function exists")

        # Test hierarchical helper function
        assert hasattr(server, 'add_nodes_to_group_hierarchically'), "hierarchical helper should exist"
        print("✅ add_nodes_to_group_hierarchically function exists")

        return True

    except Exception as e:
        print(f"❌ Helper functions test failed: {e}")
        return False

def test_project_structure():
    """Test that required project files exist."""
    print("\n📁 Testing project structure...")

    try:
        required_files = [
            'server.py',
            'pyproject.toml',
            'README.md',
            'LICENSE'
        ]

        missing_files = []
        for file in required_files:
            if not Path(file).exists():
                missing_files.append(file)

        if missing_files:
            print(f"⚠️  Missing required files: {missing_files}")
            return False

        print("✅ All required project files exist")
        return True

    except Exception as e:
        print(f"❌ Project structure test failed: {e}")
        return False

def main():
    """Run all tests and report results."""
    print("🚀 ESP RainMaker MCP Server - Adaptive Test Suite")
    print("=" * 60)

    # Check authentication status first
    is_authenticated, user_info = check_authentication_status()

    if is_authenticated:
        print(f"🎯 Running COMPREHENSIVE tests (user logged in)")
    else:
        print(f"🎯 Running BASIC tests (no authentication detected)")

    print("=" * 60)

    tests = [
        ("Import Tests", test_imports),
        ("Tool Registration", test_tool_registration),
        ("Async Compatibility", test_async_compatibility),
        ("Login Instructions", test_login_instructions),
        ("Session Handling", lambda: test_session_handling(is_authenticated, user_info)),
        ("Helper Functions", test_helper_functions),
        ("Project Structure", test_project_structure),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"💥 {test_name} crashed: {e}")
            results[test_name] = False

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY:")

    passed = sum(1 for r in results.values() if r is True)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")

    print(f"\n🎯 Final Result: {passed}/{total} tests passed")

    if is_authenticated:
        print("🔐 Comprehensive testing completed (with authentication)")
    else:
        print("🔓 Basic testing completed (without authentication)")

    if passed == total:
        print("🎉 All tests passed! ESP RainMaker MCP Server is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())