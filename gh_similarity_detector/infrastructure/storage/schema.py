SCHEMA_VERSION = 2

CREATE_META = """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
"""

CREATE_PROJECTS = """
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        url TEXT,
        language TEXT NOT NULL,
        file_count INTEGER DEFAULT 0,
        module_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_MODULES = """
    CREATE TABLE IF NOT EXISTS modules (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        module_type TEXT NOT NULL,
        source_code TEXT,
        start_line INTEGER,
        end_line INTEGER,
        token_count INTEGER,
        language TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
"""

CREATE_FINGERPRINTS = """
    CREATE TABLE IF NOT EXISTS fingerprints (
        module_id TEXT NOT NULL,
        fingerprint INTEGER NOT NULL,
        fingerprint_type TEXT NOT NULL,
        PRIMARY KEY (module_id, fingerprint, fingerprint_type),
        FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
    )
"""

CREATE_DETECTION_TASKS = """
    CREATE TABLE IF NOT EXISTS detection_tasks (
        id TEXT PRIMARY KEY,
        target_project TEXT NOT NULL,
        candidates TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        progress REAL DEFAULT 0.0,
        result_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_SIMILARITY_CACHE = """
    CREATE TABLE IF NOT EXISTS similarity_cache (
        source_module_id TEXT NOT NULL,
        target_module_id TEXT NOT NULL,
        similarity REAL NOT NULL,
        winnowing_overlap INTEGER,
        ast_similarity REAL,
        computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (source_module_id, target_module_id)
    )
"""

CREATE_DETECTION_HISTORY = """
    CREATE TABLE IF NOT EXISTS detection_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_project TEXT NOT NULL,
        candidate_count INTEGER NOT NULL DEFAULT 0,
        match_count INTEGER NOT NULL DEFAULT 0,
        avg_similarity REAL,
        max_similarity REAL,
        duration_ms INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

INDEX_FP_LOOKUP = """
    CREATE INDEX IF NOT EXISTS idx_fp_lookup
    ON fingerprints(fingerprint, fingerprint_type)
"""

INDEX_MODULE_PROJECT = """
    CREATE INDEX IF NOT EXISTS idx_module_project
    ON modules(project_id)
"""

INDEX_MODULE_LANGUAGE = """
    CREATE INDEX IF NOT EXISTS idx_module_language
    ON modules(language)
"""

INDEX_CACHE_SOURCE = """
    CREATE INDEX IF NOT EXISTS idx_cache_source
    ON similarity_cache(source_module_id)
"""

INDEX_CACHE_TARGET = """
    CREATE INDEX IF NOT EXISTS idx_cache_target
    ON similarity_cache(target_module_id)
"""

INDEX_HISTORY_TARGET = """
    CREATE INDEX IF NOT EXISTS idx_history_target
    ON detection_history(target_project)
"""

INDEX_HISTORY_CREATED = """
    CREATE INDEX IF NOT EXISTS idx_history_created
    ON detection_history(created_at)
"""

ALL_DDL = [
    CREATE_META,
    CREATE_PROJECTS,
    CREATE_MODULES,
    CREATE_FINGERPRINTS,
    INDEX_FP_LOOKUP,
    INDEX_MODULE_PROJECT,
    INDEX_MODULE_LANGUAGE,
    CREATE_DETECTION_TASKS,
    CREATE_SIMILARITY_CACHE,
    INDEX_CACHE_SOURCE,
    INDEX_CACHE_TARGET,
    CREATE_DETECTION_HISTORY,
    INDEX_HISTORY_TARGET,
    INDEX_HISTORY_CREATED,
]
