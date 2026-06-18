// 示例: Java 中型项目
package com.example.service;

import java.util.HashMap;
import java.util.Map;

public class DataService {
    private final String source;
    private final Map<String, Object> config;
    private final Map<Long, Map<String, Object>> cache;

    public DataService(String source, Map<String, Object> config) {
        this.source = source;
        this.config = config != null ? config : new HashMap<>();
        this.cache = new HashMap<>();
    }

    public Map<String, Object> process(byte[] data) {
        long key = computeChecksum(data);
        if (cache.containsKey(key)) {
            return cache.get(key);
        }
        Map<String, Object> result = new HashMap<>();
        result.put("checksum", key);
        result.put("size", data.length);
        cache.put(key, result);
        return result;
    }

    private long computeChecksum(byte[] data) {
        long h = 0;
        for (byte b : data) {
            h = (h * 31 + b) & 0xFFFFFFFFL;
        }
        return h;
    }

    public void reset() {
        cache.clear();
    }
}
