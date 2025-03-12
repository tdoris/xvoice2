"""
Unit tests for the text_injector module.
"""

import pytest
import platform
from unittest.mock import patch, MagicMock

import config
from text_injector import TextInjector

class TestTextInjector:
    """Tests for the TextInjector class."""
    
    def test_init(self):
        """Test initialization of TextInjector."""
        with patch('os.environ.get') as mock_environ_get:
            # Make it think we're not in X11 or Wayland
            mock_environ_get.return_value = None
            
            injector = TextInjector()
            
            # Should use the default from config
            assert injector.executable == config.TEXT_INJECTOR_EXECUTABLE
            assert injector.typing_delay == config.TYPING_DELAY
            assert injector.is_macos == (platform.system() == "Darwin")
    
    def test_inject_text_empty(self):
        """Test injecting empty text returns True without doing anything."""
        injector = TextInjector()
        result = injector.inject_text("")
        
        assert result is True
    
    @pytest.mark.parametrize("platform_fixture,expected_method", [
        ("mock_platform_linux", "_inject_text_linux"),
        ("mock_platform_macos", "_inject_text_macos")
    ])
    def test_inject_text_platform_routing(self, request, platform_fixture, expected_method):
        """Test that inject_text routes to the correct platform-specific method."""
        request.getfixturevalue(platform_fixture)
        
        with patch.object(TextInjector, expected_method, return_value=True) as mock_method:
            injector = TextInjector()
            result = injector.inject_text("test text")
            
            assert result is True
            mock_method.assert_called_once_with("test text")
    
    def test_inject_text_macos_success(self, mock_subprocess_run, mock_platform_macos):
        """Test successful text injection on macOS."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        injector = TextInjector()
        result = injector.inject_text("test text")
        
        assert result is True
        mock_subprocess_run.assert_called_once()
        # Check that we're calling osascript
        args, _ = mock_subprocess_run.call_args
        command_args = args[0]
        assert command_args[0] == "osascript"
    
    def test_inject_text_macos_with_delay(self, mock_subprocess_run, mock_platform_macos):
        """Test text injection on macOS with typing delay."""
        with patch('config.TYPING_DELAY', 10):
            with patch('time.sleep') as mock_sleep:
                # Patch EXECUTE_COMMANDS to False to avoid additional Return keystroke
                with patch('config.EXECUTE_COMMANDS', False):
                    injector = TextInjector()
                    result = injector.inject_text("ab")
                    
                    assert result is True
                    # Should call subprocess.run once per character
                    assert mock_subprocess_run.call_count == 2
                    # Should sleep after each character
                    assert mock_sleep.call_count == 2
    
    def test_inject_text_macos_failure(self, mock_platform_macos):
        """Test handling of subprocess errors on macOS."""
        with patch('subprocess.run', side_effect=Exception("Command failed")):
            with patch.object(TextInjector, '_inject_text_macos', side_effect=Exception("Command failed")):
                with patch.object(TextInjector, '_inject_text_macos', return_value=False):
                    injector = TextInjector()
                    result = injector.inject_text("test text")
                    
                    assert result is False
    
    def test_inject_text_linux_success(self, mock_subprocess_run, mock_platform_linux):
        """Test successful text injection on Linux."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        # Patch EXECUTE_COMMANDS to False to avoid additional Return keystroke
        with patch('config.EXECUTE_COMMANDS', False):
            injector = TextInjector()
            result = injector.inject_text("test text")
            
            assert result is True
            mock_subprocess_run.assert_called_once()
    
    def test_inject_text_linux_with_delay(self, mock_subprocess_run, mock_platform_linux):
        """Test text injection on Linux with typing delay."""
        with patch('config.TYPING_DELAY', 10):
            with patch('time.sleep') as mock_sleep:
                # Patch EXECUTE_COMMANDS to False to avoid additional Return keystroke
                with patch('config.EXECUTE_COMMANDS', False):
                    injector = TextInjector()
                    result = injector.inject_text("ab")
                    
                    assert result is True
                    # Should call subprocess.run once per character
                    assert mock_subprocess_run.call_count == 2
                    # Should sleep after each character
                    assert mock_sleep.call_count == 2
    
    def test_inject_text_linux_failure(self, mock_platform_linux):
        """Test handling of subprocess errors on Linux."""
        with patch.object(TextInjector, '_inject_text_linux', return_value=False):
            injector = TextInjector()
            result = injector.inject_text("test text")
            
            assert result is False
    
    def test_is_available_macos_success(self, mock_subprocess_run, mock_platform_macos):
        """Test checking if text injection is available on macOS."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        injector = TextInjector()
        result = injector.is_available()
        
        assert result is True
        mock_subprocess_run.assert_called_once()
    
    def test_is_available_macos_failure(self, mock_platform_macos):
        """Test checking if text injection is unavailable on macOS."""
        with patch('subprocess.run', side_effect=FileNotFoundError("Command not found")):
            injector = TextInjector()
            result = injector.is_available()
            
            assert result is False
    
    def test_is_available_linux_success(self, mock_subprocess_run, mock_platform_linux):
        """Test checking if text injection is available on Linux."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        injector = TextInjector()
        result = injector.is_available()
        
        assert result is True
        mock_subprocess_run.assert_called_once()
    
    def test_is_available_linux_failure(self, mock_platform_linux):
        """Test checking if text injection is unavailable on Linux."""
        with patch('subprocess.run', side_effect=FileNotFoundError("Command not found")):
            injector = TextInjector()
            result = injector.is_available()
            
            assert result is False
    
    def test_inject_keypress_macos(self, mock_subprocess_run, mock_platform_macos):
        """Test injecting a special keypress on macOS."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        injector = TextInjector()
        result = injector.inject_keypress("Return")
        
        assert result is True
        mock_subprocess_run.assert_called_once()
    
    def test_inject_keypress_linux(self, mock_subprocess_run, mock_platform_linux):
        """Test injecting a special keypress on Linux."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        injector = TextInjector()
        result = injector.inject_keypress("Return")
        
        assert result is True
        mock_subprocess_run.assert_called_once()