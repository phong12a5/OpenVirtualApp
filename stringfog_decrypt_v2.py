#!/usr/bin/env python3
"""
StringFog Decryption Script - Version 2
Handles nested patterns and multiple patterns per line correctly
"""

import re
import base64
import os
import shutil
from datetime import datetime

class StringFogDecryptor:
    def __init__(self):
        # Key mappings for different packages
        self.keys = {
            "com.carlos.libcommon.StringFog": "serven_scorpion",
            "com.kook.librelease.StringFog": "kook-bug-fix", 
            "StringFog": "kook-bug-fix"  # Default for simple StringFog
        }
        
        # Pattern để tìm StringFog.decrypt calls - từ phức tạp đến đơn giản
        self.patterns = [
            # Nested pattern: package1.StringFog.decrypt(package2.StringFog.decrypt("encrypted"))
            re.compile(r'([a-zA-Z0-9_.]+\.StringFog)\.decrypt\s*\(\s*([a-zA-Z0-9_.]+\.StringFog|StringFog)\.decrypt\s*\(\s*"([^"]+)"\s*\)\s*\)'),
            # Package qualified: package.StringFog.decrypt("encrypted")
            re.compile(r'([a-zA-Z0-9_.]+\.StringFog)\.decrypt\s*\(\s*"([^"]+)"\s*\)'),
            # Simple: StringFog.decrypt("encrypted")
            re.compile(r'(?<![a-zA-Z0-9_.])StringFog\.decrypt\s*\(\s*"([^"]+)"\s*\)')
        ]
    
    def xor_decrypt(self, encrypted_data, key):
        """XOR decryption algorithm exactly as used by StringFog"""
        try:
            # Base64 decode
            decoded = base64.b64decode(encrypted_data)
            
            # XOR with key
            key_bytes = key.encode('utf-8')
            data = bytearray(decoded)
            
            len_data = len(data)
            len_key = len(key_bytes)
            i = 0
            j = 0
            
            while i < len_data:
                if j >= len_key:
                    j = 0
                data[i] = data[i] ^ key_bytes[j]
                i += 1
                j += 1
            
            result = data.decode('utf-8')
            # Validate result - should be printable
            if all(ord(c) < 127 and c.isprintable() or c in '\n\r\t' for c in result):
                return result
            return None
            
        except Exception:
            return None
    
    def get_key_from_imports(self, content):
        """Determine which key to use based on import statements in the file"""
        # Check for StringFog imports
        import_patterns = [
            r'import\s+com\.lody\.virtual\.StringFog',
            r'import\s+com\.carlos\.libcommon\.StringFog', 
            r'import\s+com\.kook\.librelease\.StringFog'
        ]
        
        for pattern in import_patterns:
            if re.search(pattern, content):
                if 'lody.virtual' in pattern:
                    return 'serven_scorpion'
                elif 'carlos.libcommon' in pattern:
                    return 'serven_scorpion' 
                elif 'kook.librelease' in pattern:
                    return 'kook-bug-fix'
        
        return 'kook-bug-fix'  # Default
    
    def try_all_decrypt_methods(self, encrypted_string, file_content=None):
        """Try all possible decryption methods for an encrypted string"""
        
        # If file content provided, try to determine key from imports first
        if file_content:
            import_key = self.get_key_from_imports(file_content)
            result = self.xor_decrypt(encrypted_string, import_key)
            if result:
                return result, f"Import-based key: {import_key}"
        
        # Method 1: Try single key decryption
        for package, key in self.keys.items():
            result = self.xor_decrypt(encrypted_string, key)
            if result:
                return result, f"Single key: {package} ({key})"
        
        # Method 2: Try double decryption with different key combinations
        key_list = list(self.keys.values())
        for first_key in key_list:
            first_result = self.xor_decrypt(encrypted_string, first_key)
            if first_result:
                for second_key in key_list:
                    if second_key != first_key:
                        second_result = self.xor_decrypt(first_result, second_key)
                        if second_result:
                            return second_result, f"Double key: {first_key} -> {second_key}"
        
        return None, None
    
    def find_all_patterns(self, content):
        """Find all StringFog patterns in content, handling overlaps correctly"""
        all_matches = []
        
        for pattern_type, pattern in enumerate(self.patterns):
            for match in pattern.finditer(content):
                if pattern_type == 0:  # Nested pattern
                    all_matches.append({
                        'start': match.start(),
                        'end': match.end(),
                        'full_match': match.group(0),
                        'type': 'nested',
                        'outer_package': match.group(1),
                        'inner_package': match.group(2), 
                        'encrypted': match.group(3),
                        'pattern_type': pattern_type
                    })
                elif pattern_type == 1:  # Package qualified
                    all_matches.append({
                        'start': match.start(),
                        'end': match.end(),
                        'full_match': match.group(0),
                        'type': 'package',
                        'package': match.group(1),
                        'encrypted': match.group(2),
                        'pattern_type': pattern_type
                    })
                else:  # Simple StringFog
                    all_matches.append({
                        'start': match.start(),
                        'end': match.end(),
                        'full_match': match.group(0),
                        'type': 'simple',
                        'encrypted': match.group(1),
                        'pattern_type': pattern_type
                    })
        
        # Sort by start position, then by pattern complexity (nested first)
        all_matches.sort(key=lambda x: (x['start'], x['pattern_type']))
        
        # Remove overlaps - longer/more complex patterns take priority
        filtered_matches = []
        i = 0
        while i < len(all_matches):
            current = all_matches[i]
            
            # Check for overlaps with next matches
            j = i + 1
            while j < len(all_matches) and all_matches[j]['start'] < current['end']:
                # If next match is completely contained within current, skip it
                if all_matches[j]['end'] <= current['end']:
                    j += 1
                else:
                    # Partial overlap - keep the one that starts first (current)
                    break
            
            filtered_matches.append(current)
            i = j if j > i + 1 else i + 1
        
        return filtered_matches
    
    def decrypt_pattern(self, match_info, file_content):
        """Decrypt a single StringFog pattern"""
        if match_info['type'] == 'nested':
            # Handle nested decryption
            outer_package = match_info['outer_package']
            inner_package = match_info['inner_package']
            encrypted = match_info['encrypted']
            
            # Get keys
            outer_key = self.keys.get(outer_package, self.keys['StringFog'])
            inner_key = self.keys.get(inner_package, self.keys['StringFog'])
            
            # First decrypt with inner key
            first_result = self.xor_decrypt(encrypted, inner_key)
            if first_result:
                # Then decrypt with outer key
                final_result = self.xor_decrypt(first_result, outer_key)
                if final_result:
                    return final_result, f"Nested: {inner_package}({inner_key}) -> {outer_package}({outer_key})"
            
            # If standard nested decryption failed, try all combinations
            return self.try_all_decrypt_methods(encrypted, file_content)
            
        elif match_info['type'] == 'package':
            # Handle package qualified
            package = match_info['package']
            encrypted = match_info['encrypted']
            key = self.keys.get(package, self.keys['StringFog'])
            
            result = self.xor_decrypt(encrypted, key)
            if result:
                return result, f"Package: {package}({key})"
            
            # If standard decryption failed, try all methods
            return self.try_all_decrypt_methods(encrypted, file_content)
            
        else:  # Simple StringFog
            encrypted = match_info['encrypted']
            return self.try_all_decrypt_methods(encrypted, file_content)
    
    def process_file(self, file_path):
        """Process a single Java file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Find all patterns
            matches = self.find_all_patterns(content)
            if not matches:
                return 0
            
            print(f"\nProcessing: {file_path}")
            print(f"Found {len(matches)} StringFog patterns")
            
            # Decrypt all patterns
            replacements = []
            successful_decrypts = 0
            
            for match_info in matches:
                decrypted, method = self.decrypt_pattern(match_info, content)
                
                if decrypted:
                    print(f"  ✓ {match_info['encrypted'][:30]}... -> {decrypted[:50]}...")
                    print(f"    Method: {method}")
                    
                    # Escape quotes in decrypted string
                    escaped = decrypted.replace('\\', '\\\\').replace('"', '\\"')
                    
                    replacements.append({
                        'start': match_info['start'],
                        'end': match_info['end'],
                        'replacement': f'"{escaped}"'
                    })
                    successful_decrypts += 1
                else:
                    print(f"  ✗ Failed: {match_info['encrypted'][:30]}...")
            
            # Apply replacements (reverse order to maintain positions)
            if replacements:
                replacements.sort(key=lambda x: x['start'], reverse=True)
                
                modified_content = content
                for replacement in replacements:
                    start = replacement['start']
                    end = replacement['end']
                    new_text = replacement['replacement']
                    modified_content = modified_content[:start] + new_text + modified_content[end:]
                
                # Write back
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                
                print(f"  Updated: {successful_decrypts}/{len(matches)} patterns decrypted")
            
            return successful_decrypts
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return 0
    
    def scan_and_decrypt(self, root_dir, backup=True):
        """Scan and decrypt all Java files in directory"""
        # Create backup if requested
        if backup:
            backup_dir = f"{root_dir}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"Creating backup at: {backup_dir}")
            shutil.copytree(root_dir, backup_dir)
        
        # Find all Java files
        java_files = []
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if file.endswith('.java'):
                    java_files.append(os.path.join(root, file))
        
        print(f"Found {len(java_files)} Java files")
        
        # Process each file
        total_decrypted = 0
        files_modified = 0
        
        for file_path in java_files:
            decrypted_count = self.process_file(file_path)
            total_decrypted += decrypted_count
            if decrypted_count > 0:
                files_modified += 1
        
        print(f"\n=== SUMMARY ===")
        print(f"Files processed: {len(java_files)}")
        print(f"Files modified: {files_modified}")
        print(f"Total patterns decrypted: {total_decrypted}")

def main():
    decryptor = StringFogDecryptor()
    
    # Test with FastXmlSerializer.java first
    test_file = r"d:\PDT\VirtualApp3\commonSdk\src\main\java\com\lody\virtual\helper\utils\FastXmlSerializer.java"
    
    if os.path.exists(test_file):
        print("Testing with FastXmlSerializer.java...")
        result = decryptor.process_file(test_file)
        print(f"Decrypted {result} patterns")
    else:
        print("Test file not found, running on entire project...")
        decryptor.scan_and_decrypt(r"d:\PDT\VirtualApp3", backup=True)

if __name__ == "__main__":
    main()
