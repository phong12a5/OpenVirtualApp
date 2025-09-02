#!/usr/bin/env python3
"""
StringFog Decryptor Script
Scans all .java files and decrypts StringFog encrypted strings
Supports multiple keys used in the project
"""

import os
import re
import base64
import glob

class StringFogDecryptor:
    def __init__(self):
        # Keys được sử dụng trong project với mapping theo package
        self.package_keys = {
            "com.carlos.libcommon.StringFog": "serven_scorpion",
            "com.lody.virtual.StringFog": "serven_scorpion", 
            "com.kook.librelease.StringFog": "kook-bug-fix",
            "com.kook.collect.StringFog": "kook-bug-fix",
            "com.kook.network.StringFog": "kook-bug-fix",
            "com.kook.core.log.StringFog": "kook-bug-fix",
            "com.lody.virtual.common.StringFog": "kook-bug-fix",
            "com.carlos.common.network.StringFog": "kook-bug-fix",
            "StringFog": "kook-bug-fix"  # Default for unqualified StringFog
        }
    
    def xor_decrypt(self, encrypted_data, key):
        """XOR decryption algorithm used by StringFog"""
        try:
            # Decode base64
            decoded = base64.b64decode(encrypted_data)
            
            # XOR với key - exact implementation from StringFog
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
            
            return data.decode('utf-8')
        except Exception as e:
            print(f"Error decrypting {encrypted_data}: {e}")
            return None
    
    def get_key_for_package(self, package_name):
        """Lấy key dựa trên package name"""
        # Special handling for simple StringFog in nested context
        if package_name == "StringFog":
            # Try to determine from other context or use a reasonable default
            # For ImageHeaderParser case, StringFog refers to com.kook.librelease.StringFog
            return "kook-bug-fix"
        
        return self.package_keys.get(package_name, "kook-bug-fix")  # Default key
    
    def try_decrypt_with_all_keys(self, encrypted_string):
        """Thử decrypt với tất cả các key có thể"""
        for package_name, key_value in self.package_keys.items():
            try:
                decrypted = self.xor_decrypt(encrypted_string, key_value)
                if decrypted and self.is_valid_decryption(decrypted):
                    return decrypted, key_value
            except:
                continue
        return None, None
    
    def is_valid_decryption(self, text):
        """Kiểm tra xem kết quả decrypt có hợp lệ không"""
        if not text:
            return False
        
        # Strip null bytes and whitespace
        cleaned_text = text.rstrip('\x00').strip()
        if not cleaned_text:
            return False
            
        # Cho phép các ký tự printable và whitespace thông thường
        return all(c.isprintable() or c in '\n\r\t ' for c in cleaned_text)
    
    def get_key_from_imports(self, content):
        """Xác định key dựa trên import statements trong file"""
        # Kiểm tra các import StringFog
        if re.search(r'import\s+com\.lody\.virtual\.StringFog', content):
            return "serven_scorpion"
        elif re.search(r'import\s+com\.carlos\.libcommon\.StringFog', content):
            return "serven_scorpion"
        elif re.search(r'import\s+com\.kook\.librelease\.StringFog', content):
            return "kook-bug-fix"
        
        return "kook-bug-fix"  # Default
    
    def decrypt_nested_stringfog(self, full_match):
        """Xử lý decrypt nested StringFog patterns"""
        # Pattern cho nested: outer.StringFog.decrypt(inner.StringFog.decrypt("encrypted"))
        nested_pattern = r'([a-zA-Z0-9_.]+\.StringFog)\.decrypt\s*\(\s*([a-zA-Z0-9_.]*\.?StringFog)\.decrypt\s*\(\s*"([^"]+)"\s*\)\s*\)'
        
        match = re.match(nested_pattern, full_match)
        if not match:
            return None, None
            
        outer_package = match.group(1)
        inner_package = match.group(2) if match.group(2) else "StringFog"
        encrypted_string = match.group(3)
        
        print(f"  Nested pattern detected:")
        print(f"    Outer: {outer_package}")
        print(f"    Inner: {inner_package}")
        print(f"    Encrypted: {encrypted_string}")
        
        # Step 1: Decrypt with inner package key
        inner_key = self.get_key_for_package(inner_package)
        print(f"    Inner key: {inner_key}")
        
        try:
            inner_decrypted = self.xor_decrypt(encrypted_string, inner_key)
            if not inner_decrypted:
                print("    Inner decryption failed")
                return None, None
            print(f"    Inner result: {inner_decrypted}")
        except:
            print("    Inner decryption exception")
            return None, None
            
        # Step 2: Decrypt result with outer package key  
        outer_key = self.get_key_for_package(outer_package)
        print(f"    Outer key: {outer_key}")
        
        try:
            final_decrypted = self.xor_decrypt(inner_decrypted, outer_key)
            if final_decrypted and self.is_valid_decryption(final_decrypted):
                # Clean up null bytes and whitespace
                cleaned_result = final_decrypted.rstrip('\x00').strip()
                print(f"    Final result: {cleaned_result}")
                return cleaned_result, f"{inner_package}({inner_key}) -> {outer_package}({outer_key})"
        except:
            print("    Outer decryption exception")
            pass
            
        return None, None
    
    def find_stringfog_patterns(self, content):
        """Tìm tất cả các pattern StringFog.decrypt() trong code"""
        patterns = [
            # Pattern 1: Nested StringFog - package.StringFog.decrypt(package.StringFog.decrypt("encrypted"))
            r'[a-zA-Z0-9_.]+\.StringFog\.decrypt\s*\(\s*[a-zA-Z0-9_.]*\.?StringFog\.decrypt\s*\(\s*"([^"]+)"\s*\)\s*\)',
            # Pattern 2: package.StringFog.decrypt("encrypted_string")  
            r'[a-zA-Z0-9_.]+\.StringFog\.decrypt\s*\(\s*"([^"]+)"\s*\)',
            # Pattern 3: Simple StringFog.decrypt("encrypted_string")
            r'(?<![a-zA-Z0-9_.])[Ss]tringFog\.decrypt\s*\(\s*"([^"]+)"\s*\)'
        ]
        
        matches = []
        for i, pattern in enumerate(patterns):
            for match in re.finditer(pattern, content):
                # For nested pattern, we need special handling
                if i == 0:  # Nested pattern
                    matches.append({
                        'full_match': match.group(0),
                        'encrypted_string': match.group(1),
                        'start': match.start(),
                        'end': match.end(),
                        'type': 'nested'
                    })
                else:  # Simple patterns
                    matches.append({
                        'full_match': match.group(0),
                        'encrypted_string': match.group(1),
                        'start': match.start(),
                        'end': match.end(),
                        'type': 'simple'
                    })
        
        # Remove overlapping matches (nested takes priority)
        matches.sort(key=lambda x: (x['start'], -len(x['full_match'])))
        filtered_matches = []
        last_end = -1
        
        for match in matches:
            if match['start'] >= last_end:
                filtered_matches.append(match)
                last_end = match['end']
        
        return filtered_matches
    
    def process_file(self, file_path):
        """Xử lý một file Java"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            matches = self.find_stringfog_patterns(content)
            if not matches:
                return 0, content
            
            print(f"\nProcessing: {file_path}")
            print(f"Found {len(matches)} StringFog patterns")
            
            # Sắp xếp matches theo vị trí từ đầu đến cuối
            matches.sort(key=lambda x: x['start'])
            
            # Xử lý tất cả matches và tạo danh sách replacements
            replacements = []
            
            for match in matches:
                if match['type'] == 'nested':
                    # Handle nested StringFog patterns
                    decrypted, key_used = self.decrypt_nested_stringfog(match['full_match'])
                else:
                    # Handle simple StringFog patterns
                    encrypted_string = match['encrypted_string']
                    
                    # Try to extract package name from full_match to determine key
                    full_match = match['full_match']
                    package_match = re.search(r'([a-zA-Z0-9_.]+\.StringFog)', full_match)
                    if package_match:
                        package_name = package_match.group(1)
                        key = self.get_key_for_package(package_name)
                        decrypted = self.xor_decrypt(encrypted_string, key)
                        key_used = f"{package_name}({key})"
                    else:
                        # For simple StringFog.decrypt(), check import statements
                        import_key = self.get_key_from_imports(content)
                        decrypted = self.xor_decrypt(encrypted_string, import_key)
                        if decrypted and self.is_valid_decryption(decrypted):
                            key_used = f"Import-based({import_key})"
                        else:
                            # Fallback to trying all keys
                            decrypted, key_used = self.try_decrypt_with_all_keys(encrypted_string)
                
                if decrypted:
                    print(f"  Decrypted: {match['encrypted_string'][:50]}... -> {decrypted}")
                    print(f"  Key used: {key_used}")
                    
                    # Escape special characters trong decrypted string
                    escaped_decrypted = decrypted.replace('\\', '\\\\').replace('"', '\\"')
                    replacement = f'"{escaped_decrypted}"'
                    
                    replacements.append({
                        'start': match['start'],
                        'end': match['end'], 
                        'replacement': replacement
                    })
                else:
                    print(f"  Failed to decrypt: {match['encrypted_string'][:50]}...")
            
            # Rebuild content từ các replacements (từ cuối về đầu để không ảnh hưởng index)
            replacements.sort(key=lambda x: x['start'], reverse=True)
            modified_content = content
            
            for replacement in replacements:
                start_pos = replacement['start']
                end_pos = replacement['end']
                modified_content = modified_content[:start_pos] + replacement['replacement'] + modified_content[end_pos:]
            
            return len(replacements), modified_content
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return 0, None
    
    def scan_and_decrypt(self, root_dir, backup=True):
        """Scan tất cả file .java và decrypt StringFog"""
        java_files = []
        
        # Tìm tất cả file .java
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if file.endswith('.java'):
                    java_files.append(os.path.join(root, file))
        
        print(f"Found {len(java_files)} .java files")
        
        total_replacements = 0
        processed_files = 0
        
        for file_path in java_files:
            replacements_count, modified_content = self.process_file(file_path)
            
            if replacements_count > 0 and modified_content:
                processed_files += 1
                total_replacements += replacements_count
                
                # Backup original file if requested
                if backup:
                    backup_path = file_path + '.backup'
                    if not os.path.exists(backup_path):
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            original_content = f.read()
                        with open(backup_path, 'w', encoding='utf-8') as f:
                            f.write(original_content)
                        print(f"  Backup created: {backup_path}")
                
                # Write modified content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                
                print(f"  Modified: {file_path} ({replacements_count} replacements)")
        
        print(f"\nSummary:")
        print(f"  Total files processed: {processed_files}")
        print(f"  Total replacements: {total_replacements}")
        
        return processed_files, total_replacements

def main():
    print("StringFog Decryptor for Java files")
    print("=" * 50)
    
    # Get current directory
    current_dir = os.getcwd()
    print(f"Working directory: {current_dir}")
    
    # Initialize decryptor
    decryptor = StringFogDecryptor()
    
    # Ask user for confirmation
    response = input("\nDo you want to decrypt all StringFog patterns in .java files? (y/n): ")
    if response.lower() != 'y':
        print("Operation cancelled.")
        return
    
    # Ask about backup
    backup_response = input("Create backup files (.backup)? (y/n): ")
    create_backup = backup_response.lower() == 'y'
    
    # Start processing
    print("\nStarting decryption process...")
    processed_files, total_replacements = decryptor.scan_and_decrypt(current_dir, backup=create_backup)
    
    if total_replacements > 0:
        print(f"\n✅ Successfully decrypted {total_replacements} strings in {processed_files} files!")
        if create_backup:
            print("💾 Original files backed up with .backup extension")
        
        print("\n🎉 All StringFog patterns have been decrypted!")
        print("📁 Your Java files now contain the original readable strings.")
    else:
        print("\n❌ No StringFog patterns found or decrypted.")

if __name__ == "__main__":
    main()
