// Owner: Person B. Develop against ./mock/sample_response.json first, then switch USE_MOCK to false.
const USE_MOCK = false;

async function check(file, lang = "en") {
  if (USE_MOCK) return (await fetch("mock/sample_response.json")).json();
  const fd = new FormData();
  fd.append("file", file);
  fd.append("lang", lang);
  const r = await fetch("/api/check", { method: "POST", body: fd });
  return r.json();
}

document.getElementById("go").onclick = async () => {
  const f = document.getElementById("file").files[0];
  if (!f && !USE_MOCK) return;
  const data = await check(f);
  // TODO: render risk card, segment timeline, advice, feedback buttons, error states
  document.getElementById("result").textContent = JSON.stringify(data, null, 2);
};
