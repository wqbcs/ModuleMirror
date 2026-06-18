"""
Winnowing 指纹生成算法

基于 MOSS 系统使用的 Winnowing 算法，生成代码指纹。
核心：对 token 序列使用滑动窗口计算哈希，选择局部最小值作为指纹点。

Reference: Saul Schleimer, Daniel S. Wilkerson, and Alex Aiken.
"Winnowing: Local Algorithms for Document Fingerprinting." SIGMOD 2003.

Author: GitHub 项目代码相似度检测工具
"""

from typing import List, Set, Tuple, Dict
from ...models.entities import FingerprintSet, Module


class RollingHash:
    """滚动哈希实现 (Rabin-Karp)"""
    
    DEFAULT_BASE = 257
    DEFAULT_MODULUS = 2**31 - 1
    
    def __init__(self, base: int = DEFAULT_BASE, modulus: int = DEFAULT_MODULUS):
        self.base = base
        self.modulus = modulus
    
    @staticmethod
    def _deterministic_hash(item: str) -> int:
        h = 0
        for ch in item:
            h = (h * 31 + ord(ch)) & 0xFFFFFFFF
        return h
    
    def hash_sequence(self, sequence: List[str]) -> int:
        hash_value = 0
        for item in sequence:
            hash_value = (hash_value * self.base + self._deterministic_hash(item)) % self.modulus
        return hash_value


class CodeTokenizer:
    """基于 tree-sitter 的代码 Tokenizer
    
    将代码转换为 token 序列，忽略空格和注释。
    标识符统一化为 'ID'，字符串统一化为 'STR'，数字统一化为 'NUM'。
    """
    
    PYTHON_KEYWORDS = {
        'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
        'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
        'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
        'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
        'try', 'while', 'with', 'yield'
    }
    
    JAVA_KEYWORDS = {
        'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch',
        'char', 'class', 'const', 'continue', 'default', 'do', 'double',
        'else', 'enum', 'extends', 'final', 'finally', 'float', 'for',
        'goto', 'if', 'implements', 'import', 'instanceof', 'int', 'interface',
        'long', 'native', 'new', 'package', 'private', 'protected', 'public',
        'return', 'short', 'static', 'strictfp', 'super', 'switch',
        'synchronized', 'this', 'throw', 'throws', 'transient', 'try',
        'void', 'volatile', 'while'
    }
    
    JS_KEYWORDS = {
        'async', 'await', 'break', 'case', 'catch', 'class', 'const',
        'continue', 'debugger', 'default', 'delete', 'do', 'else', 'export',
        'extends', 'false', 'finally', 'for', 'function', 'if', 'import',
        'in', 'instanceof', 'let', 'new', 'null', 'of', 'return', 'static',
        'super', 'switch', 'this', 'throw', 'true', 'try', 'typeof',
        'undefined', 'var', 'void', 'while', 'with', 'yield'
    }
    
    TWO_CHAR_OPS = (
        '==', '!=', '<=', '>=', '+=', '-=', '*=', '/=',
        '//', '**', '->', '=>', '<<', '>>', '&&', '||',
        '++', '--', '??', '?.',
    )

    KEYWORDS_MAP = {
        'python': PYTHON_KEYWORDS,
        'java': JAVA_KEYWORDS,
        'javascript': JS_KEYWORDS,
    }
    
    def tokenize(self, code: str, language: str = 'python') -> List[str]:
        """将代码转换为 token 序列
        
        Args:
            code: 源代码
            language: 编程语言
        
        Returns:
            token 序列
        """
        keywords = self.KEYWORDS_MAP.get(language, set())
        tokens = []
        i = 0
        n = len(code)
        
        while i < n:
            if code[i].isspace():
                i += 1
                continue
            
            if language == 'python' and code[i:i+1] == '#':
                while i < n and code[i] != '\n':
                    i += 1
                continue
            
            if language == 'python' and code[i:i+3] in ('"""', "'''"):
                quote = code[i:i+3]
                i += 3
                while i + 2 < n and code[i:i+3] != quote:
                    i += 1
                if i + 2 < n and code[i:i+3] == quote:
                    i += 3
                continue
            
            if language in ('java', 'javascript') and code[i:i+2] == '//':
                while i < n and code[i] != '\n':
                    i += 1
                continue
            
            if language in ('java', 'javascript') and code[i:i+2] == '/*':
                i += 2
                while i + 1 < n and code[i:i+2] != '*/':
                    i += 1
                if i + 1 < n and code[i:i+2] == '*/':
                    i += 2
                continue
            
            if code[i] in ('"', "'"):
                quote = code[i]
                i += 1
                while i < n and code[i] != quote:
                    if code[i] == '\\' and i + 1 < n:
                        i += 2
                    else:
                        i += 1
                if i < n:
                    i += 1
                tokens.append('STR')
                continue
            
            if code[i].isalpha() or code[i] == '_':
                start = i
                while i < n and (code[i].isalnum() or code[i] == '_'):
                    i += 1
                word = code[start:i]
                if word in keywords:
                    tokens.append(word)
                else:
                    tokens.append('ID')
                continue
            
            if code[i].isdigit():
                while i < n and (code[i].isdigit() or code[i] == '.'):
                    i += 1
                tokens.append('NUM')
                continue
            
            if i < n - 1 and code[i:i+2] in self.TWO_CHAR_OPS:
                tokens.append(code[i:i+2])
                i += 2
                continue
            
            tokens.append(code[i])
            i += 1
        
        return tokens


class Winnowing:
    """Winnowing 指纹生成算法
    
    参数说明:
    - kgram_size (k): 每个 k-gram 的长度，决定检测粒度
      较小的 k 检测更短的相似片段，但误报率更高
    - window_size (w): 选择局部最小值的窗口大小
      w 决定指纹的密度，较大的 w 产生更少的指纹
    """
    
    def __init__(self, window_size: int = 5, kgram_size: int = 15):
        self.window_size = window_size
        self.kgram_size = kgram_size
        self.tokenizer = CodeTokenizer()
        self.hasher = RollingHash()
    
    def generate_fingerprints(self, module: Module) -> FingerprintSet:
        """为模块生成指纹集合
        
        Args:
            module: 代码模块
        
        Returns:
            指纹集合
        """
        tokens = self.tokenizer.tokenize(module.source_code, module.language)
        
        if len(tokens) < self.kgram_size:
            if tokens:
                fp = self.hasher.hash_sequence(tokens)
                return FingerprintSet(
                    module_id=module.id,
                    winnowing_fingerprints={fp},
                    token_count=len(tokens)
                )
            return FingerprintSet(module_id=module.id)
        
        kgram_hashes = []
        for i in range(len(tokens) - self.kgram_size + 1):
            kgram = tokens[i:i + self.kgram_size]
            hash_value = self.hasher.hash_sequence(kgram)
            kgram_hashes.append((hash_value, i))
        
        fingerprints = self._winnow(kgram_hashes)
        
        return FingerprintSet(
            module_id=module.id,
            winnowing_fingerprints=fingerprints,
            token_count=len(tokens)
        )
    
    def _winnow(self, kgram_hashes: List[Tuple[int, int]]) -> Set[int]:
        """Winnowing 核心：选择局部最小值

        使用滑动窗口最小值算法 O(n) 替代朴素 O(n*w)。
        维护一个单调递增队列，队首为当前窗口最小值。

        Args:
            kgram_hashes: [(哈希值, 位置)] 列表

        Returns:
            指纹集合
        """
        fingerprints = set()
        n = len(kgram_hashes)

        if n <= self.window_size:
            for hash_val, _ in kgram_hashes:
                fingerprints.add(hash_val)
            return fingerprints

        from collections import deque
        deq = deque()
        last_selected_pos = -1

        for i in range(n):
            while deq and kgram_hashes[deq[-1]][0] >= kgram_hashes[i][0]:
                deq.pop()
            deq.append(i)

            while deq and deq[0] <= i - self.window_size:
                deq.popleft()

            window_end = i
            if window_end >= self.window_size - 1:
                min_idx = deq[0]
                if min_idx != last_selected_pos:
                    fingerprints.add(kgram_hashes[min_idx][0])
                    last_selected_pos = min_idx

        return fingerprints
    
    def generate_fingerprints_from_code(
        self,
        code: str,
        language: str = 'python',
        module_id: str = ''
    ) -> FingerprintSet:
        """直接从代码字符串生成指纹
        
        Args:
            code: 源代码
            language: 编程语言
            module_id: 模块 ID
        
        Returns:
            指纹集合
        """
        tokens = self.tokenizer.tokenize(code, language)
        
        if len(tokens) < self.kgram_size:
            if tokens:
                fp = self.hasher.hash_sequence(tokens)
                return FingerprintSet(
                    module_id=module_id,
                    winnowing_fingerprints={fp},
                    token_count=len(tokens)
                )
            return FingerprintSet(module_id=module_id)
        
        kgram_hashes = []
        for i in range(len(tokens) - self.kgram_size + 1):
            kgram = tokens[i:i + self.kgram_size]
            hash_value = self.hasher.hash_sequence(kgram)
            kgram_hashes.append((hash_value, i))
        
        fingerprints = self._winnow(kgram_hashes)
        
        return FingerprintSet(
            module_id=module_id,
            winnowing_fingerprints=fingerprints,
            token_count=len(tokens)
        )
    
    def generate_fingerprints_with_positions(
        self,
        code: str,
        language: str = 'python',
        module_id: str = ''
    ) -> Tuple[FingerprintSet, Dict[int, int]]:
        tokens = self.tokenizer.tokenize(code, language)
        
        if len(tokens) < self.kgram_size:
            if tokens:
                fp = self.hasher.hash_sequence(tokens)
                return (
                    FingerprintSet(
                        module_id=module_id,
                        winnowing_fingerprints={fp},
                        token_count=len(tokens)
                    ),
                    {fp: 0}
                )
            return FingerprintSet(module_id=module_id), {}
        
        kgram_hashes = []
        for i in range(len(tokens) - self.kgram_size + 1):
            kgram = tokens[i:i + self.kgram_size]
            hash_value = self.hasher.hash_sequence(kgram)
            kgram_hashes.append((hash_value, i))
        
        fingerprints = set()
        positions: Dict[int, int] = {}
        
        n = len(kgram_hashes)
        if n <= self.window_size:
            for hash_val, pos in kgram_hashes:
                fingerprints.add(hash_val)
                positions[hash_val] = pos
        else:
            from collections import deque
            deq = deque()
            last_selected_pos = -1
            
            for i in range(n):
                while deq and kgram_hashes[deq[-1]][0] >= kgram_hashes[i][0]:
                    deq.pop()
                deq.append(i)
                
                while deq and deq[0] <= i - self.window_size:
                    deq.popleft()
                
                window_end = i
                if window_end >= self.window_size - 1:
                    min_idx = deq[0]
                    if min_idx != last_selected_pos:
                        hash_val = kgram_hashes[min_idx][0]
                        fingerprints.add(hash_val)
                        positions[hash_val] = kgram_hashes[min_idx][1]
                        last_selected_pos = min_idx
        
        return (
            FingerprintSet(
                module_id=module_id,
                winnowing_fingerprints=fingerprints,
                token_count=len(tokens)
            ),
            positions
        )


def compute_continuity_score(
    positions1: Dict[int, int],
    positions2: Dict[int, int],
    common_hashes: Set[int],
) -> float:
    if not common_hashes:
        return 0.0
    
    sorted_hashes = sorted(common_hashes, key=lambda h: positions1.get(h, 0))
    
    consecutive_runs = []
    current_run = [sorted_hashes[0]]
    
    for i in range(1, len(sorted_hashes)):
        prev_hash = sorted_hashes[i - 1]
        curr_hash = sorted_hashes[i]
        
        pos1_diff = positions1.get(curr_hash, 0) - positions1.get(prev_hash, 0)
        pos2_diff = abs(
            positions2.get(curr_hash, 0) - positions2.get(prev_hash, 0)
        )
        
        if pos1_diff <= 2 and pos2_diff <= 2:
            current_run.append(curr_hash)
        else:
            if len(current_run) > 1:
                consecutive_runs.append(current_run)
            current_run = [curr_hash]
    
    if len(current_run) > 1:
        consecutive_runs.append(current_run)
    
    if not consecutive_runs:
        return 0.0
    
    max_run_length = max(len(run) for run in consecutive_runs)
    total_common = len(common_hashes)
    
    continuity = (max_run_length / total_common) * 100.0
    
    return min(continuity, 100.0)
