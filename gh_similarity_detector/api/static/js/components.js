/**
 * ModuleMirror UI 组件库
 * shadcn/ui 风格 + Tailwind CSS 设计系统
 */

const MM = (() => {
  const _theme = { dark: false };

  function hsl(varName) {
    return `hsl(var(${varName}))`;
  }

  function cn(...classes) {
    return classes.filter(Boolean).join(' ');
  }

  const Theme = {
    toggle() {
      _theme.dark = !_theme.dark;
      document.documentElement.classList.toggle('dark', _theme.dark);
      localStorage.setItem('mm-theme', _theme.dark ? 'dark' : 'light');
    },
    init() {
      const saved = localStorage.getItem('mm-theme');
      if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        _theme.dark = true;
        document.documentElement.classList.add('dark');
      }
    },
    isDark() { return _theme.dark; }
  };

  const Badge = {
    create(text, variant = 'default') {
      const variants = {
        default: 'bg-primary/10 text-primary border-primary/20',
        secondary: 'bg-secondary text-muted-foreground border-secondary',
        destructive: 'bg-destructive/10 text-destructive border-destructive/20',
        success: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-800',
        warning: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-800',
        outline: 'bg-transparent text-foreground border-border',
      };
      const el = document.createElement('span');
      el.className = cn('inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors', variants[variant] || variants.default);
      el.textContent = text;
      return el;
    }
  };

  const Button = {
    create(text, { variant = 'default', size = 'default', icon = null, onclick = null } = {}) {
      const variants = {
        default: 'bg-primary text-primary-foreground hover:bg-primary-hover shadow-sm',
        secondary: 'bg-secondary text-muted-foreground hover:bg-secondary-hover shadow-sm',
        destructive: 'bg-destructive text-white hover:bg-red-600 shadow-sm',
        outline: 'border border-border bg-transparent hover:bg-accent hover:text-accent-foreground',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'text-primary underline-offset-4 hover:underline',
      };
      const sizes = {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 px-3 text-xs',
        lg: 'h-10 px-6',
        icon: 'h-9 w-9',
      };
      const el = document.createElement('button');
      el.className = cn('inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50', variants[variant], sizes[size]);
      if (icon) {
        el.innerHTML = `${icon}<span>${text}</span>`;
      } else {
        el.textContent = text;
      }
      if (onclick) el.addEventListener('click', onclick);
      return el;
    }
  };

  const Card = {
    create({ title = '', description = '', content = '', footer = '', icon = '', class: cls = '' } = {}) {
      const el = document.createElement('div');
      el.className = cn('rounded-xl border border-border bg-card text-card-foreground shadow-sm transition-all hover:shadow-md', cls);
      let html = '';
      if (title || description) {
        html += `<div class="flex flex-col space-y-1.5 p-6">`;
        if (icon) html += `<div class="text-2xl mb-2">${icon}</div>`;
        if (title) html += `<h3 class="font-semibold leading-none tracking-tight">${title}</h3>`;
        if (description) html += `<p class="text-sm text-muted-foreground">${description}</p>`;
        html += `</div>`;
      }
      if (content) html += `<div class="p-6 pt-0">${content}</div>`;
      if (footer) html += `<div class="flex items-center p-6 pt-0">${footer}</div>`;
      el.innerHTML = html;
      return el;
    },
    stats({ label, value, icon = '', trend = null, trendLabel = '' }) {
      const el = document.createElement('div');
      el.className = 'rounded-xl border border-border bg-card p-6 shadow-sm transition-all hover:shadow-md hover:border-primary/30';
      let trendHtml = '';
      if (trend !== null) {
        const isUp = trend >= 0;
        const trendColor = isUp ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400';
        const arrow = isUp ? '&#9650;' : '&#9660;';
        trendHtml = `<div class="flex items-center gap-1 mt-1"><span class="${trendColor} text-xs font-medium">${arrow} ${Math.abs(trend)}%</span>${trendLabel ? `<span class="text-muted-foreground text-xs">${trendLabel}</span>` : ''}</div>`;
      }
      el.innerHTML = `<div class="flex items-center justify-between"><div><p class="text-sm font-medium text-muted-foreground">${label}</p><p class="text-2xl font-bold tracking-tight mt-1">${value}</p>${trendHtml}</div>${icon ? `<div class="text-3xl opacity-80">${icon}</div>` : ''}</div>`;
      return el;
    }
  };

  const Input = {
    create({ placeholder = '', type = 'text', value = '', id = '', oninput = null } = {}) {
      const el = document.createElement('input');
      el.type = type;
      el.className = 'flex h-9 w-full rounded-md border border-border bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50';
      if (placeholder) el.placeholder = placeholder;
      if (value) el.value = value;
      if (id) el.id = id;
      if (oninput) el.addEventListener('input', oninput);
      return el;
    }
  };

  const Progress = {
    create({ value = 0, max = 100, id = '' } = {}) {
      const el = document.createElement('div');
      el.className = 'relative h-2 w-full overflow-hidden rounded-full bg-secondary';
      if (id) el.id = id;
      const indicator = document.createElement('div');
      indicator.className = 'h-full bg-primary transition-all duration-500 ease-in-out rounded-full';
      indicator.style.width = `${Math.min(100, (value / max) * 100)}%`;
      el.appendChild(indicator);
      el._indicator = indicator;
      el.setValue = (v) => { indicator.style.width = `${Math.min(100, (v / max) * 100)}%`; };
      return el;
    }
  };

  const Table = {
    create({ headers = [], id = '' } = {}) {
      const container = document.createElement('div');
      container.className = 'relative w-full overflow-auto';
      if (id) container.id = id;
      const table = document.createElement('table');
      table.className = 'w-full caption-bottom text-sm';
      const thead = document.createElement('thead');
      thead.className = 'border-b border-border';
      const headerRow = document.createElement('tr');
      headers.forEach(h => {
        const th = document.createElement('th');
        th.className = 'h-10 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0';
        th.textContent = h;
        headerRow.appendChild(th);
      });
      thead.appendChild(headerRow);
      table.appendChild(thead);
      const tbody = document.createElement('tbody');
      tbody.className = '[&_tr:last-child]:border-0';
      table.appendChild(tbody);
      container.appendChild(table);
      container._tbody = tbody;
      container.addRow = (cells, { class: cls = '' } = {}) => {
        const tr = document.createElement('tr');
        tr.className = cn('border-b border-border transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted', cls);
        cells.forEach(cell => {
          const td = document.createElement('td');
          td.className = 'p-4 align-middle [&:has([role=checkbox])]:pr-0';
          if (cell instanceof HTMLElement) { td.appendChild(cell); }
          else { td.textContent = cell; }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
        return tr;
      };
      container.clearRows = () => { tbody.innerHTML = ''; };
      container.setEmpty = (text) => {
        tbody.innerHTML = '';
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = headers.length;
        td.className = 'h-24 text-center text-muted-foreground';
        td.textContent = text;
        tr.appendChild(td);
        tbody.appendChild(tr);
      };
      return container;
    }
  };

  const Dialog = {
    _overlay: null,
    _container: null,
    init() {
      this._overlay = document.createElement('div');
      this._overlay.className = 'fixed inset-0 z-50 bg-black/50 backdrop-blur-sm hidden transition-all';
      this._container = document.createElement('div');
      this._container.className = 'fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 hidden w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-xl transition-all';
      document.body.appendChild(this._overlay);
      document.body.appendChild(this._container);
      this._overlay.addEventListener('click', () => this.close());
    },
    open({ title = '', content = '', onConfirm = null, confirmText = '确认', cancelText = '取消' } = {}) {
      this._container.innerHTML = `<div class="flex flex-col space-y-4"><div class="flex flex-col space-y-1.5"><h3 class="text-lg font-semibold leading-none tracking-tight">${title}</h3></div><div class="text-sm text-muted-foreground">${content}</div><div class="flex justify-end gap-2"><button id="mm-dialog-cancel" class="inline-flex items-center justify-center rounded-md border border-border bg-transparent h-9 px-4 py-2 text-sm font-medium hover:bg-accent transition-all">${cancelText}</button><button id="mm-dialog-confirm" class="inline-flex items-center justify-center rounded-md bg-primary text-primary-foreground h-9 px-4 py-2 text-sm font-medium hover:bg-primary-hover shadow-sm transition-all">${confirmText}</button></div></div>`;
      this._overlay.classList.remove('hidden');
      this._container.classList.remove('hidden');
      document.getElementById('mm-dialog-cancel').addEventListener('click', () => this.close());
      if (onConfirm) {
        document.getElementById('mm-dialog-confirm').addEventListener('click', () => { onConfirm(); this.close(); });
      }
    },
    close() {
      this._overlay.classList.add('hidden');
      this._container.classList.add('hidden');
    }
  };

  const Toast = {
    _container: null,
    init() {
      this._container = document.createElement('div');
      this._container.className = 'fixed bottom-4 right-4 z-50 flex flex-col gap-2';
      document.body.appendChild(this._container);
    },
    show(message, { variant = 'default', duration = 3000 } = {}) {
      const variants = {
        default: 'bg-card border-border text-foreground',
        success: 'bg-emerald-50 border-emerald-200 text-emerald-700 dark:bg-emerald-950/50 dark:border-emerald-800 dark:text-emerald-400',
        error: 'bg-red-50 border-red-200 text-red-700 dark:bg-red-950/50 dark:border-red-800 dark:text-red-400',
        warning: 'bg-amber-50 border-amber-200 text-amber-700 dark:bg-amber-950/50 dark:border-amber-800 dark:text-amber-400',
      };
      const icons = { default: '', success: '&#10003;', error: '&#10007;', warning: '&#9888;' };
      const el = document.createElement('div');
      el.className = cn('flex items-center gap-2 rounded-lg border px-4 py-3 shadow-lg transition-all animate-in slide-in-from-right', variants[variant]);
      el.innerHTML = `${icons[variant] ? `<span class="text-base">${icons[variant]}</span>` : ''}<span class="text-sm font-medium">${message}</span>`;
      this._container.appendChild(el);
      setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(100%)'; setTimeout(() => el.remove(), 300); }, duration);
    }
  };

  const Tabs = {
    create({ tabs = [], defaultTab = 0, id = '' } = {}) {
      const container = document.createElement('div');
      container.className = 'w-full';
      if (id) container.id = id;
      const nav = document.createElement('div');
      nav.className = 'inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground';
      const panels = document.createElement('div');
      panels.className = 'mt-4';
      tabs.forEach((tab, i) => {
        const trigger = document.createElement('button');
        trigger.className = cn('inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', i === defaultTab ? 'bg-card text-foreground shadow' : 'hover:bg-card/50');
        trigger.textContent = tab.label;
        trigger.addEventListener('click', () => {
          nav.querySelectorAll('button').forEach(b => b.className = cn('inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', 'hover:bg-card/50'));
          trigger.className = cn('inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', 'bg-card text-foreground shadow');
          panels.querySelectorAll(':scope > div').forEach(p => p.classList.add('hidden'));
          panels.children[i].classList.remove('hidden');
        });
        nav.appendChild(trigger);
        const panel = document.createElement('div');
        panel.className = i === defaultTab ? '' : 'hidden';
        if (tab.content instanceof HTMLElement) { panel.appendChild(tab.content); }
        else { panel.innerHTML = tab.content; }
        panels.appendChild(panel);
      });
      container.appendChild(nav);
      container.appendChild(panels);
      return container;
    }
  };

  const Skeleton = {
    create({ class: cls = '' } = {}) {
      const el = document.createElement('div');
      el.className = cn('animate-pulse rounded-md bg-muted', cls || 'h-4 w-48');
      return el;
    }
  };

  const Tooltip = {
    init() {
      document.addEventListener('mouseover', (e) => {
        const target = e.target.closest('[data-mm-tooltip]');
        if (!target) return;
        const text = target.getAttribute('data-mm-tooltip');
        const tip = document.createElement('div');
        tip.className = 'absolute z-50 overflow-hidden rounded-md border border-border bg-card px-3 py-1.5 text-xs shadow-md animate-in fade-in-0 zoom-in-95';
        tip.textContent = text;
        tip.id = 'mm-tooltip-active';
        const rect = target.getBoundingClientRect();
        tip.style.left = `${rect.left + rect.width / 2}px`;
        tip.style.top = `${rect.top - 8}px`;
        tip.style.transform = 'translate(-50%, -100%)';
        document.body.appendChild(tip);
      });
      document.addEventListener('mouseout', (e) => {
        if (e.target.closest('[data-mm-tooltip]')) {
          const tip = document.getElementById('mm-tooltip-active');
          if (tip) tip.remove();
        }
      });
    }
  };

  function init() {
    Theme.init();
    Dialog.init();
    Toast.init();
    Tooltip.init();
  }

  return { Theme, Badge, Button, Card, Input, Progress, Table, Dialog, Toast, Tabs, Skeleton, Tooltip, cn, hsl, init };
})();

if (typeof window !== 'undefined') {
  window.MM = MM;
}
