// 示例: JS 前端项目
export class DataService {
  constructor(source, config = {}) {
    this.source = source;
    this.config = config;
    this._cache = new Map();
  }

  async process(data) {
    const key = this._computeChecksum(data);
    if (this._cache.has(key)) {
      return this._cache.get(key);
    }
    const result = { checksum: key, size: data.length };
    this._cache.set(key, result);
    return result;
  }

  _computeChecksum(data) {
    let h = 0;
    for (const byte of data) {
      h = (h * 31 + byte) & 0xffffffff;
    }
    return h;
  }

  reset() {
    this._cache.clear();
  }
}
