#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = []
# description = "Convert Claude Code JSONL sessions to readable markdown transcripts"
# authors = ["Claude Code Community"]
# license = "MIT"
# ///
"""
Standalone Claude Session Transcript Generator

Converts Claude Code JSONL session files to readable markdown transcripts
with the exact same output as the physical-sessions command.

Usage:
    python session_transcript.py session.jsonl
    python session_transcript.py session.jsonl --upload-gist
    python session_transcript.py session.jsonl -o output.md
    
With uv (recommended):
    uv run session_transcript.py session.jsonl
    uv run session_transcript.py session.jsonl --upload-gist
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


class Entry:
    """Represents a single JSONL entry"""
    def __init__(self, data: Dict[str, Any]):
        self.type = data.get('type', 'unknown')
        self.uuid = data.get('uuid', '')
        self.parent_uuid = data.get('parentUuid', '')
        self.message = data.get('message', {})
        self.content = data.get('content', {})
        self.is_sidechain = data.get('isSidechain', False)
        self.is_meta = data.get('isMeta', False)
        
        # Parse timestamp
        self.timestamp = None
        if 'timestamp' in data:
            try:
                timestamp_str = data['timestamp']
                if timestamp_str.endswith('Z'):
                    timestamp_str = timestamp_str[:-1] + '+00:00'
                self.timestamp = datetime.fromisoformat(timestamp_str)
            except (ValueError, TypeError):
                pass


class SessionSummary:
    """Summary information about a session"""
    def __init__(self, uuid: str, summary: str = "Claude Code Session", 
                 artifact_type: str = "unknown", created_at: str = "", 
                 edited_files: List[str] = None):
        self.uuid = uuid
        self.summary = summary
        self.artifact_type = artifact_type
        self.created_at = created_at
        self.edited_files = edited_files or []
        self.details = {}


class TimingInfo:
    """Timing information for turns"""
    def __init__(self, is_first: bool = False, start_time_local: Optional[datetime] = None,
                 offset_from_start: Optional[str] = None, duration: Optional[str] = None):
        self.is_first = is_first
        self.start_time_local = start_time_local
        self.offset_from_start = offset_from_start
        self.duration = duration


class ConversationTurn:
    """A single conversation turn"""
    def __init__(self, user_message: Optional[str] = None, 
                 assistant_sequence: List[Dict[str, Any]] = None,
                 timing_info: Optional[TimingInfo] = None,
                 start_time: Optional[datetime] = None,
                 end_time: Optional[datetime] = None):
        self.user_message = user_message
        self.assistant_sequence = assistant_sequence or []
        self.timing_info = timing_info
        self.start_time = start_time
        self.end_time = end_time


class SessionProcessor:
    """Processes JSONL sessions into markdown transcripts with exact same logic as backend"""
    
    def parse_jsonl(self, file_path: str) -> Tuple[SessionSummary, List[Entry]]:
        """Parse JSONL file into session summary and entries"""
        entries = []
        session_summary = None
        session_uuid = Path(file_path).stem
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = Entry(data)
                    entries.append(entry)
                    
                    # Extract summary if available
                    if entry.type == 'summary':
                        summary_text = entry.content.get('summary', 'Claude Code Session')
                        session_summary = SessionSummary(
                            uuid=session_uuid,
                            summary=summary_text
                        )
                except json.JSONDecodeError:
                    continue
        
        # Create default summary if none found
        if not session_summary:
            session_summary = SessionSummary(uuid=session_uuid)
        
        return session_summary, entries
    
    def group_entries_into_turns(self, entries: List[Entry]) -> List[ConversationTurn]:
        """Group JSONL entries into conversational turns, correlating sidechains with main thread"""
        # First, separate main thread from sidechains and filter out meta entries
        main_entries = [e for e in entries if not e.is_sidechain and e.type != 'summary' and not e.is_meta]
        sidechain_entries = [e for e in entries if e.is_sidechain]
        
        # Group sidechain entries by their conversation thread
        sidechain_groups = self._group_sidechain_entries(sidechain_entries)
        
        # Build main conversation turns with timing information
        turns = []
        current_turn = {}
        conversation_start_time = None
        
        for entry in main_entries:
            if entry.type == 'user':
                # Check if this is a tool result (should be part of current turn)
                user_content = self._extract_user_content(entry)
                if not user_content.strip() or 'tool_use_id' in str(entry.message):
                    # This is likely a tool result, skip it for turn grouping
                    continue
                
                # Start a new turn for real user messages
                if current_turn:
                    turns.append(current_turn)
                
                # Set conversation start time from first user message
                if conversation_start_time is None:
                    conversation_start_time = entry.timestamp
                
                current_turn = {
                    'user_message': user_content,
                    'assistant_sequence': [],  # Chronological sequence of text and tool operations
                    'start_time': entry.timestamp,
                    'end_time': entry.timestamp  # Will be updated as we process assistant responses
                }
            
            elif entry.type == 'assistant':
                # Only process assistant entries if we have a current turn
                if not current_turn:
                    continue
                    
                # Process assistant content
                message = entry.message or {}
                content = message.get('content', [])
                
                if not isinstance(content, list):
                    content = [content]
                
                # Process content blocks in chronological order
                for block in content:
                    if isinstance(block, dict):
                        if block.get('type') == 'text':
                            text_content = block.get('text', '').strip()
                            if text_content:
                                current_turn['assistant_sequence'].append({
                                    'type': 'text',
                                    'content': text_content
                                })
                        elif block.get('type') == 'tool_use':
                            # Format tool operation
                            tool_op = self._format_tool_operation(block)
                            if tool_op:
                                tool_item = {
                                    'type': 'tool',
                                    'content': tool_op
                                }
                                
                                # Check if this tool use has an associated sidechain
                                tool_id = block.get('id')
                                tool_name = block.get('name', '')
                                if tool_name == 'Task' and tool_id:
                                    # Look for related sidechain
                                    related_sidechain = self._find_related_sidechain(entry, sidechain_groups)
                                    if related_sidechain:
                                        tool_item['sidechain_summary'] = self._summarize_sidechain(related_sidechain)
                                
                                current_turn['assistant_sequence'].append(tool_item)
                    else:
                        text_content = str(block).strip()
                        if text_content:
                            current_turn['assistant_sequence'].append({
                                'type': 'text',
                                'content': text_content
                            })
                
                # Update turn end time with this assistant entry
                if entry.timestamp and current_turn:
                    current_turn['end_time'] = entry.timestamp
        
        # Add the final turn if it has content
        if current_turn and (current_turn.get('user_message') or current_turn.get('assistant_sequence')):
            turns.append(current_turn)
        
        # Add timing information to each turn
        for i, turn in enumerate(turns):
            if conversation_start_time and turn.get('start_time'):
                if i == 0:
                    # First turn shows actual local time
                    turn['timing_info'] = TimingInfo(
                        is_first=True,
                        start_time_local=turn['start_time'],
                        offset_from_start=None,
                        duration=self._calculate_duration(turn.get('start_time'), turn.get('end_time'))
                    )
                else:
                    # Subsequent turns show offset from conversation start
                    offset_seconds = (turn['start_time'] - conversation_start_time).total_seconds()
                    turn['timing_info'] = TimingInfo(
                        is_first=False,
                        start_time_local=None,
                        offset_from_start=self._format_time_offset(offset_seconds),
                        duration=self._calculate_duration(turn.get('start_time'), turn.get('end_time'))
                    )
        
        # Convert to ConversationTurn objects and filter out empty turns
        conversation_turns = []
        for turn in turns:
            if (turn.get('user_message', '').strip() or turn.get('assistant_sequence')):
                conversation_turns.append(ConversationTurn(
                    user_message=turn.get('user_message'),
                    assistant_sequence=turn.get('assistant_sequence', []),
                    timing_info=turn.get('timing_info'),
                    start_time=turn.get('start_time'),
                    end_time=turn.get('end_time')
                ))
        
        return conversation_turns
    
    def format_session_as_markdown(self, session: SessionSummary, entries: List[Entry]) -> str:
        """Format session entries as readable markdown with proper turn structure"""
        session_uuid = session.uuid
        details = session.details or {}
        
        # Header
        markdown = f"# Session Transcript: {session.summary}\n\n"
        markdown += f"**Session ID**: `{session_uuid}`  \n"
        markdown += f"**Created**: {details.get('created_at', session.created_at or 'Unknown')}  \n"
        markdown += f"**Type**: {session.artifact_type}  \n"
        
        edited_files = details.get('edited_files', session.edited_files)
        if edited_files and isinstance(edited_files, list):
            files_str = ', '.join(edited_files)
        else:
            files_str = "None"
        markdown += f"**Files Modified**: {files_str}  \n\n"
        
        markdown += "---\n\n"
        
        # Group entries into conversational turns
        turns = self.group_entries_into_turns(entries)
        
        for i, turn in enumerate(turns):
            # Format turn header (simple)
            timing_info = turn.timing_info
            header = f"## Turn {i + 1}"
            markdown += f"{header}\n\n"
            
            # Add timing information underneath as plain text
            if timing_info:
                timing_lines = []
                if timing_info.is_first and timing_info.start_time_local:
                    # First turn shows local time
                    local_time = timing_info.start_time_local.strftime('%I:%M:%S %p')
                    timing_lines.append(f"Started: {local_time}")
                elif timing_info.offset_from_start:
                    # Subsequent turns show offset from start
                    timing_lines.append(f"Offset: +{timing_info.offset_from_start}")
                
                if timing_info.duration:
                    timing_lines.append(f"Duration: {timing_info.duration}")
                
                if timing_lines:
                    markdown += " · ".join(timing_lines) + "\n\n"
            
            # User message
            if turn.user_message:
                markdown += f"**User Request:**\n{turn.user_message}\n\n"
            
            # Assistant sequence (chronological text and tool operations)
            assistant_sequence = turn.assistant_sequence
            if assistant_sequence:
                in_assistant_response = False
                in_actions_section = False
                
                for item in assistant_sequence:
                    item_type = item.get('type')
                    content = item.get('content', '')
                    
                    if item_type == 'text':
                        # Close actions section if we were in one
                        if in_actions_section:
                            in_actions_section = False
                            markdown += "\n"
                        
                        if not in_assistant_response:
                            markdown += f"**Assistant Response:**\n{content}\n\n"
                            in_assistant_response = True
                        else:
                            markdown += f"**Assistant Response:**\n{content}\n\n"
                            in_assistant_response = True
                    
                    elif item_type == 'tool':
                        # Close assistant response section if we were in one
                        if in_assistant_response:
                            in_assistant_response = False
                        
                        # Only add "Actions Taken:" header if not already in actions section
                        if not in_actions_section:
                            markdown += f"**Actions Taken:**\n\n"
                            in_actions_section = True
                        
                        markdown += content
                        
                        # Add sidechain details if present
                        if item.get('sidechain_summary'):
                            markdown += f"\n**Parallel Task Details:**\n\n"
                            markdown += f"- **Task execution**: {item['sidechain_summary']}\n"
            
            markdown += "---\n\n"
        
        return markdown
    
    # Helper methods (extracted from SessionProcessor)
    def _group_sidechain_entries(self, sidechain_entries: List[Entry]) -> Dict[datetime, List[Entry]]:
        """Group sidechain entries by conversation thread"""
        groups = {}
        for entry in sidechain_entries:
            # Use a simple heuristic - group by timestamp proximity (within 1 minute)
            timestamp = entry.timestamp
            if timestamp:
                # Round to minute for grouping
                minute_key = timestamp.replace(second=0, microsecond=0)
                if minute_key not in groups:
                    groups[minute_key] = []
                groups[minute_key].append(entry)
        return groups
    
    def _find_related_sidechain(self, main_entry: Entry, sidechain_groups: Dict[datetime, List[Entry]]) -> Optional[List[Entry]]:
        """Find sidechain entries related to a main thread tool use"""
        if not main_entry.timestamp:
            return None
        
        # Look for sidechains that started around the same time
        main_minute = main_entry.timestamp.replace(second=0, microsecond=0)
        
        # Check the same minute and next minute
        for time_offset in [0, 1]:
            check_time = main_minute.replace(minute=main_minute.minute + time_offset)
            if check_time in sidechain_groups:
                return sidechain_groups[check_time]
        
        return None
    
    def _summarize_sidechain(self, sidechain_entries: List[Entry]) -> str:
        """Create a summary of what happened in the sidechain"""
        if not sidechain_entries:
            return "No sidechain details available"
        
        # Count tool operations and extract key actions
        tool_count = 0
        file_operations = []
        
        for entry in sidechain_entries:
            if entry.type == 'assistant' and entry.message:
                content = entry.message.get('content', [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'tool_use':
                            tool_count += 1
                            tool_name = block.get('name', '')
                            if tool_name in ['Read', 'Edit', 'Write', 'Grep']:
                                tool_input = block.get('input', {})
                                file_path = tool_input.get('file_path', '')
                                if file_path:
                                    file_operations.append(f"{tool_name}: {file_path}")
        
        summary_parts = []
        if tool_count > 0:
            summary_parts.append(f"Executed {tool_count} tool operations")
        
        if file_operations:
            # Show first few file operations
            shown_ops = file_operations[:3]
            summary_parts.append("Key operations: " + ", ".join(shown_ops))
            if len(file_operations) > 3:
                summary_parts.append(f"... and {len(file_operations) - 3} more")
        
        return "; ".join(summary_parts) if summary_parts else "Parallel task execution"
    
    def _extract_user_content(self, entry: Entry) -> str:
        """Extract clean user content from entry"""
        message = entry.message or {}
        content = message.get('content', '')
        
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                    # Skip tool results in user display
                else:
                    text_parts.append(str(item))
            content = '\n'.join(text_parts)
        
        content = content.strip()
        
        # Filter out pseudo-command recordings
        if self._is_pseudo_command(content):
            return ""
        
        return content
    
    def _is_pseudo_command(self, content: str) -> bool:
        """Check if content is a pseudo-command recording that should be filtered out"""
        if not content:
            return False
            
        # Check for command execution XML tags
        pseudo_command_patterns = [
            '<command-name>', '<command-message>', '<command-args>', '<local-command-stdout>',
            '</command-name>', '</command-message>', '</command-args>', '</local-command-stdout>'
        ]
        
        # If content contains any pseudo-command XML tags, filter it out
        for pattern in pseudo_command_patterns:
            if pattern in content:
                return True
                
        return False
    
    def _calculate_duration(self, start_time: Optional[datetime], end_time: Optional[datetime]) -> str:
        """Calculate human-friendly duration between two timestamps"""
        if not start_time or not end_time:
            return "Unknown duration"
        
        duration_seconds = (end_time - start_time).total_seconds()
        return self._format_duration(duration_seconds)
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-friendly format"""
        if seconds < 1:
            return "< 1 second"
        elif seconds < 60:
            return f"{int(seconds)} second{'s' if int(seconds) != 1 else ''}"
        elif seconds < 3600:  # Less than 1 hour
            minutes = int(seconds // 60)
            remaining_seconds = int(seconds % 60)
            if remaining_seconds == 0:
                return f"{minutes} minute{'s' if minutes != 1 else ''}"
            else:
                return f"{minutes} minute{'s' if minutes != 1 else ''} {remaining_seconds} second{'s' if remaining_seconds != 1 else ''}"
        else:  # 1 hour or more
            hours = int(seconds // 3600)
            remaining_minutes = int((seconds % 3600) // 60)
            if remaining_minutes == 0:
                return f"{hours} hour{'s' if hours != 1 else ''}"
            else:
                return f"{hours} hour{'s' if hours != 1 else ''} {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"
    
    def _format_time_offset(self, seconds: float) -> str:
        """Format time offset from conversation start in human-friendly format"""
        return self._format_duration(seconds)
    
    def _format_tool_operation(self, tool_block: Dict[str, Any]) -> str:
        """Format a single tool operation with special handling for specific tools"""
        tool_name = tool_block.get('name', 'Unknown')
        tool_input = tool_block.get('input', {})
        
        if tool_name == 'MultiEdit':
            return self._format_multiedit_operation(tool_input)
        elif tool_name == 'TodoWrite':
            return self._format_todowrite_operation(tool_input)
        elif tool_name == 'Task':
            return self._format_task_operation(tool_input)
        elif tool_name == 'Bash':
            return self._format_bash_operation(tool_input)
        elif tool_name in ['Edit', 'Write', 'Read']:
            file_path = tool_input.get('file_path', 'Unknown')
            return f"- **{tool_name}**: `{file_path}`\n"
        elif tool_name in ['Grep', 'Glob']:
            return self._format_search_operation(tool_name, tool_input)
        else:
            return f"- **{tool_name}**: {json.dumps(tool_input, indent=2)}\n"
    
    def _format_multiedit_operation(self, tool_input: Dict[str, Any]) -> str:
        """Format MultiEdit operations in a readable way"""
        file_path = tool_input.get('file_path', 'Unknown')
        edits = tool_input.get('edits', [])
        
        # Handle case where edits is a JSON string instead of a list
        if isinstance(edits, str):
            try:
                edits = json.loads(edits)
            except (json.JSONDecodeError, ValueError):
                return f"- **MultiEdit**: `{file_path}` (corrupted edits data)\n"
        
        if not isinstance(edits, list):
            return f"- **MultiEdit**: `{file_path}` (invalid edits format)\n"
        
        result = f"- **MultiEdit**: `{file_path}` ({len(edits)} changes)\n\n"
        
        for i, edit in enumerate(edits, 1):
            if not isinstance(edit, dict):
                result += f"  **Change {i}:** (Invalid edit format)\n"
                continue
            
            old_string = edit.get('old_string', '')
            new_string = edit.get('new_string', '')
            
            # Truncate very long strings for readability
            old_preview = self._truncate_for_display(old_string, 100)
            new_preview = self._truncate_for_display(new_string, 100)
            
            result += f"  **Change {i}:**\n"
            result += f"  ```diff\n"
            result += f"  - {old_preview}\n"
            result += f"  + {new_preview}\n"
            result += f"  ```\n"
        
        return result.rstrip() + "\n"
    
    def _format_todowrite_operation(self, tool_input: Dict[str, Any]) -> str:
        """Format TodoWrite operations in a readable way"""
        todos = tool_input.get('todos', [])
        
        result = f"- **TodoWrite**: Updated task list ({len(todos)} items)\n\n"
        
        # Create a simple table-like format
        result += "  | Status | Priority | Task |\n"
        result += "  |--------|----------|------|\n"
        
        for todo in todos:
            status = todo.get('status', 'pending')
            priority = todo.get('priority', 'medium')
            content = todo.get('content', 'No description')
            
            # Truncate long content
            content_preview = self._truncate_for_display(content, 60)
            
            result += f"  | {status} | {priority} | {content_preview} |\n"
        
        return result.rstrip() + "\n"
    
    def _format_task_operation(self, tool_input: Dict[str, Any]) -> str:
        """Format Task operations in a readable way"""
        description = tool_input.get('description', 'No description')
        prompt = tool_input.get('prompt', 'No prompt provided')
        
        result = f"- **Task**: {description}\n\n"
        result += "  ```\n"
        
        # Show first few lines of the prompt
        prompt_lines = prompt.split('\n')
        preview_lines = prompt_lines[:5]  # Show first 5 lines
        
        for line in preview_lines:
            result += f"  {line}\n"
            
        if len(prompt_lines) > 5:
            result += f"  ... ({len(prompt_lines) - 5} more lines)\n"
        
        result += "  ```\n"
        
        return result.rstrip() + "\n"
    
    def _format_search_operation(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Format Grep/Glob operations in a readable way"""
        pattern = tool_input.get('pattern', 'No pattern')
        path = tool_input.get('path', 'No path specified')
        include = tool_input.get('include', '')
        
        result = f"- **{tool_name}**: Search for `{pattern}`"
        if path != 'No path specified':
            result += f" in `{path}`"
        if include:
            result += f" (files: `{include}`)"
        
        return result + "\n"
    
    def _format_bash_operation(self, tool_input: Dict[str, Any]) -> str:
        """Format Bash operations as clean markdown code blocks"""
        command = tool_input.get('command', 'No command')
        description = tool_input.get('description', 'Bash command')
        
        result = f"- **Bash**: {description}\n\n"
        result += "  ```bash\n"
        result += f"  {command}\n"
        result += "  ```\n"
        
        return result
    
    def _truncate_for_display(self, text: str, max_length: int) -> str:
        """Truncate text for display, handling newlines properly"""
        # Replace \n with proper newlines for markdown
        text = text.replace('\\n', '\n')
        
        # If text is short, return as-is
        if len(text) <= max_length:
            return text
        
        # For longer text, try to break at word boundaries
        truncated = text[:max_length]
        
        # If we're in the middle of a word, back up to the last space
        if len(text) > max_length and text[max_length] != ' ':
            last_space = truncated.rfind(' ')
            if last_space > max_length * 0.7:  # Don't go too far back
                truncated = truncated[:last_space]
        
        return truncated + "..."


def upload_to_gist(content: str, filename: str) -> bool:
    """Upload content to GitHub Gist using gh CLI"""
    try:
        # Check if gh CLI is available
        subprocess.run(['gh', '--version'], capture_output=True, check=True)
        
        # Create gist
        process = subprocess.run([
            'gh', 'gist', 'create', '--filename', filename, '--public', '-'
        ], input=content, text=True, capture_output=True, check=True)
        
        gist_url = process.stdout.strip()
        print(f"✅ Uploaded to GitHub Gist: {gist_url}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error uploading to gist: {e}")
        return False
    except FileNotFoundError:
        print("❌ GitHub CLI (gh) not found. Install with: brew install gh")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Convert Claude Code JSONL sessions to markdown transcripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python session_transcript.py session.jsonl
  python session_transcript.py session.jsonl -o custom_name.md
  python session_transcript.py session.jsonl --upload-gist
        """
    )
    
    parser.add_argument('jsonl_file', help='Path to Claude Code JSONL session file')
    parser.add_argument('-o', '--output', help='Output markdown file (default: auto-generated)')
    parser.add_argument('--upload-gist', action='store_true', 
                       help='Upload the transcript to GitHub Gist after generation')
    
    args = parser.parse_args()
    
    # Validate input file
    jsonl_path = Path(args.jsonl_file)
    if not jsonl_path.exists():
        print(f"❌ Error: File not found: {jsonl_path}")
        return 1
    
    # Generate output filename
    if args.output:
        output_path = Path(args.output)
    else:
        session_id = jsonl_path.stem[:8]
        output_path = Path(f"session_{session_id}_transcript.md")
    
    # Process the session
    processor = SessionProcessor()
    
    try:
        print(f"📝 Processing session: {jsonl_path}")
        session_summary, entries = processor.parse_jsonl(str(jsonl_path))
        
        print(f"📊 Found {len(entries)} entries")
        
        # Generate markdown
        markdown = processor.format_session_as_markdown(session_summary, entries)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        file_size = output_path.stat().st_size
        print(f"✅ Transcript generated: {output_path}")
        print(f"📏 File size: {file_size:,} bytes")
        
        # Upload to gist if requested
        if args.upload_gist:
            print("🚀 Uploading to GitHub Gist...")
            upload_to_gist(markdown, output_path.name)
        
        return 0
        
    except Exception as e:
        print(f"❌ Error processing session: {e}")
        return 1


def cli():
    """Entry point for the CLI."""
    sys.exit(main())


if __name__ == '__main__':
    cli()