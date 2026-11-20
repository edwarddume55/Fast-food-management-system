(function () {
  'use strict';
  var data = JSON.parse(document.getElementById('pos-data').textContent);
  var csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
  var products = data.products;
  var byId = {};
  products.forEach(function (p) { byId[p.id] = p; });

  var cart = {};          // product id -> quantity
  var state = { cat: 'all', pay: data.payments[0].id, type: data.types[0].id };

  var $ = function (id) { return document.getElementById(id); };
  var money = function (n) {
    return data.currency + ' ' + n.toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };
  var round2 = function (n) { return Math.round(n * 100) / 100; };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function qtyOf(id) { return cart[id] || 0; }
  function remaining(p) { return p.left === null ? Infinity : p.left - qtyOf(p.id); }

  function totals() {
    var subtotal = 0;
    Object.keys(cart).forEach(function (id) { subtotal += byId[id].price * cart[id]; });
    var discount = Math.min(Math.max(Number($('discount').value) || 0, 0), subtotal);
    return { subtotal: round2(subtotal), discount: round2(discount), total: round2(subtotal - discount) };
  }

  /* ---------- rendering ---------- */
  function renderTabs() {
    var box = $('tabs');
    box.textContent = '';
    [{ id: 'all', name: 'All' }].concat(data.categories).forEach(function (c) {
      var b = el('button', 'tab' + (state.cat === c.id ? ' on' : ''), c.name);
      b.type = 'button';
      b.onclick = function () { state.cat = c.id; renderTabs(); renderTiles(); };
      box.appendChild(b);
    });
  }

  function renderTiles() {
    var box = $('tiles');
    box.textContent = '';
    products.forEach(function (p) {
      if (state.cat !== 'all' && p.cat !== state.cat) return;
      var out = remaining(p) <= 0;
      var b = el('button', 'tile' + (out ? ' out' : ''));
      b.type = 'button';
      b.appendChild(el('b', '', p.name));
      b.appendChild(el('span', 'price', money(p.price)));
      if (p.left !== null && p.left <= 10) {
        b.appendChild(el('span', 'left', p.left === 0 ? 'Sold out' : p.left + ' left'));
      }
      if (qtyOf(p.id)) b.appendChild(el('span', 'qtybadge', qtyOf(p.id)));
      if (out) b.setAttribute('aria-disabled', 'true');
      b.onclick = function () { add(p.id, 1); };
      box.appendChild(b);
    });
  }

  function renderLines() {
    var box = $('lines');
    box.textContent = '';
    var ids = Object.keys(cart);
    if (!ids.length) {
      box.appendChild(el('p', 'empty', 'Tap an item to start the order.'));
      return;
    }
    ids.forEach(function (id) {
      var p = byId[id];
      var row = el('div', 'line');
      row.appendChild(el('strong', '', p.name));
      row.appendChild(el('span', '', money(p.price * cart[id])));
      var st = el('div', 'stepper');
      var minus = el('button', '', '\u2212'); minus.type = 'button'; minus.setAttribute('aria-label', 'Remove one ' + p.name);
      minus.onclick = function () { add(p.id, -1); };
      var plus = el('button', '', '+'); plus.type = 'button'; plus.setAttribute('aria-label', 'Add one ' + p.name);
      plus.onclick = function () { add(p.id, 1); };
      var rm = el('button', 'rm', 'Remove'); rm.type = 'button';
      rm.onclick = function () { delete cart[p.id]; render(); };
      st.appendChild(minus); st.appendChild(el('span', '', cart[id])); st.appendChild(plus); st.appendChild(rm);
      row.appendChild(st);
      box.appendChild(row);
    });
  }

  function renderSeg(boxId, items, key) {
    var box = $(boxId);
    box.textContent = '';
    items.forEach(function (it) {
      var b = el('button', state[key] === it.id ? 'on' : '', it.label);
      b.type = 'button';
      b.onclick = function () { state[key] = it.id; renderSeg(boxId, items, key); renderTotals(); };
      box.appendChild(b);
    });
  }

  function renderTotals() {
    var t = totals();
    $('subtotal').textContent = money(t.subtotal);
    $('total').textContent = money(t.total);
    var cash = state.pay === 'CASH';
    $('cashbox').hidden = !cash;

    var tendered = $('tendered').value === '' ? null : Number($('tendered').value);
    var enough = !cash || (tendered !== null && round2(tendered) >= t.total);
    $('change').textContent = cash && tendered !== null && enough ? money(round2(tendered - t.total)) : '-';

    var quick = $('quick');
    quick.textContent = '';
    if (cash && t.total > 0) {
      var opts = [t.total, Math.ceil(t.total / 100) * 100, 500, 1000, 2000, 5000]
        .filter(function (v) { return v >= t.total; });
      opts.filter(function (v, i) { return opts.indexOf(v) === i; }).slice(0, 4).forEach(function (v) {
        var b = el('button', '', v === t.total ? 'Exact' : String(v));
        b.type = 'button';
        b.onclick = function () { $('tendered').value = v; renderTotals(); };
        quick.appendChild(b);
      });
    }
    $('charge').disabled = !Object.keys(cart).length || !enough;
    $('charge').textContent = Object.keys(cart).length ? 'Charge ' + money(t.total) : 'Charge';
  }

  function render() { renderTiles(); renderLines(); renderTotals(); }

  function add(id, delta) {
    var p = byId[id];
    var next = qtyOf(id) + delta;
    if (delta > 0 && remaining(p) <= 0) return;
    if (next <= 0) delete cart[id]; else cart[id] = next;
    render();
  }

  /* ---------- checkout ---------- */
  var toastEl = null;
  function toast(message, opts) {
    opts = opts || {};
    if (toastEl) toastEl.remove();
    toastEl = el('div', 'toast' + (opts.error ? ' err' : ''));
    toastEl.setAttribute('role', opts.error ? 'alert' : 'status');
    toastEl.appendChild(el('span', '', message));
    if (opts.link) {
      var a = el('a', '', 'Receipt'); a.href = opts.link; a.target = '_blank'; a.rel = 'noopener';
      toastEl.appendChild(a);
    }
    var x = el('button', '', 'Dismiss'); x.type = 'button';
    x.onclick = function () { toastEl.remove(); toastEl = null; };
    toastEl.appendChild(x);
    document.body.appendChild(toastEl);
    if (!opts.error) setTimeout(function () { if (toastEl) { toastEl.remove(); toastEl = null; } }, 15000);
  }

  function applyAvailability(left) {
    products.forEach(function (p) {
      if (Object.prototype.hasOwnProperty.call(left, p.id)) p.left = left[p.id];
    });
    Object.keys(cart).forEach(function (id) {       // never keep more than we can make
      var p = byId[id];
      if (p.left !== null && cart[id] > p.left) { if (p.left <= 0) delete cart[id]; else cart[id] = p.left; }
    });
  }

  function charge() {
    var btn = $('charge');
    btn.disabled = true;
    var t = totals();
    var body = {
      lines: Object.keys(cart).map(function (id) { return { id: Number(id), qty: cart[id] }; }),
      discount: t.discount,
      payment: state.pay,
      order_type: state.type,
      tendered: state.pay === 'CASH' ? Number($('tendered').value) : null
    };
    fetch(data.checkout_url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify(body)
    }).then(function (res) {
      return res.json().then(function (json) { return { ok: res.ok, json: json }; });
    }).then(function (r) {
      if (r.json.left) applyAvailability(r.json.left);
      if (r.ok && r.json.ok) {
        cart = {};
        $('discount').value = '';
        $('tendered').value = '';
        var change = Number(r.json.change);
        toast(r.json.number + ' paid' + (change > 0 ? ' \u00b7 change ' + money(change) : ''), { link: r.json.receipt_url });
      } else {
        toast(r.json.error || 'Could not complete the sale.', { error: true });
      }
      render();
    }).catch(function () {
      toast('No connection. The order was not saved. Check the network and try again.', { error: true });
      render();
    });
  }

  $('charge').onclick = charge;
  $('discount').oninput = renderTotals;
  $('tendered').oninput = renderTotals;
  renderSeg('types', data.types, 'type');
  renderSeg('pays', data.payments, 'pay');
  renderTabs();
  render();
})();
