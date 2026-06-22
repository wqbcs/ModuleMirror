from .calculator import SimilarityCalculator as SimilarityCalculator
from .differ import CodeDiffer as CodeDiffer
from .ast_comparator import ASTDeepComparator as ASTDeepComparator

try:
    from .lsh_index import MinHashLSHIndex as MinHashLSHIndex
    from .lsh_index import HybridIndex as HybridIndex
except ImportError:
    ...
