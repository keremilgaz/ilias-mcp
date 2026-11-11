# ilias-mcp

[English](README.md) · **Türkçe** · [Deutsch](README.de.md)

**ILIAS derslerini yapay zekâ asistanına sor.**

Ders materyallerini bul, ödev son tarihlerini kontrol et ve son kayıtlı
kontrolünden bu yana nelerin değiştiğini gör; hepsini yapay zekâ sohbetinden.

**Konstanz Üniversitesi** için bağımsız bir öğrenci projesi. MCP istemcini,
kendi ILIAS hesabınla erişebildiğin ders içeriğine bağlar. Erişim yalnızca
okuma amaçlıdır: ödev teslim etmek, mesaj yazmak ya da derse kaydolmak için
hiçbir araç yoktur.

## Neler sorabilirim?

- “Bu hafta hangi derslerimde ödev teslimi var?”
- “Son kontrolümden bu yana bu derste neler değişti?”
- “En son ders slaytlarını bul ve benim için özetle.”
- “Bu dersin duyurularını ve forum başlıklarını göster.”

Asistan bilgileri ilias-mcp üzerinden alır ve sorunu yanıtlamak için kullanır.

## Kullanım senaryoları

**Haftalık kontrol.** Haftada bir şunu sor:

> Bu dönemki tüm ILIAS derslerimi kontrol et ve son kontrolümden bu yana neyin yeni olduğunu söyle.

Asistan bu dönemin bütün derslerini tek seferde kontrol eder. Yalnızca yeni ya
da değişmiş dosyaları, ödevleri, forum başlıklarını ve duyuruları, ayrıca
önümüzdeki 14 gün içindeki son tarihleri raporlar. Önemli olanları not
ettikten sonra kontrolü kaydeder; gelecek haftaki kontrol oradan başlar. İlk
kontrol her şeyi yeni olarak listeler.

**Son tarihlere toplu bakış.**

> Açık bütün ödevleri son tarihleriyle birlikte, tarihe göre sıralı listele ve bu hafta teslim edilecekleri işaretle.

Derslerindeki ödev sayfalarını okur: son tarihler, başlangıç tarihleri ve bir
şey teslim edip etmediğin. Asistanın bir takvim ya da yapılacaklar uygulamasına
da bağlıysa tarihleri oraya aktarabilir.

**Derse hazırlık.**

> Bir sonraki İstatistik dersinin slaytlarını bul, özetle ve sorabileceğim üç soru öner.

Dersteki en yeni dosyayı bulur ve metniyle çalışır. Okunan sayfalar hatırlanır;
sonraki bir istekte yalnızca yeni olan kısım gelir.

**Sadece PDF'lerde yazan görevler.** Bazı talimatlar yalnızca slaytlarda ya da
dağıtılan belgelerde yer alır:

> Bu dönemki ders PDF'lerinde teslim, son tarih ya da sunum geçen yerleri ara ve bulduklarını listele.

Anahtar kelime araması, belgelerin tamamı yerine eşleşen bölümleri sayfa
numaralarıyla döndürür.

**Ara verdikten sonra yetişmek.**

> Seminerin iki haftasını kaçırdım. Derste neler değişti, duyurularda ne yazıyordu?

Dersi son kayıtlı kontrolünle karşılaştırır, yeni materyalleri ve duyuruları
gösterir, aktif forum başlıklarını listeler. Başlıklar açılmaz, bu yüzden
hiçbir şey okunmuş olarak işaretlenmez.

**Materyalleri klasörüne kaydetmek.**

> Bu dersin yeni slaytlarını ILIAS klasörümde "İstatistik" altına indir.

Dosyalar yalnızca ayarlanan indirme klasörünün içine kaydedilir; aynı adı
taşıyan farklı bir dosyanın üzerine asla yazılmaz.

**Sınav hazırlığı.**

> Bu dersin bütün ders slaytlarını gözden geçir ve her konunun geçtiği slaytlarla birlikte bir konu listesi çıkar.

Dosyalar sırayla, uzun olanlar parça parça okunur. Okuma kaydı nelerin
tamamlandığını sohbetler arasında da takip eder.

Yapmadıkları: ödev teslim etmek, forumlara yazmak, derslere kaydolmak ya da
forum başlıklarını açmak.

## Claude Desktop'a kurulum

1. [GitHub Releases](https://github.com/keremilgaz/ilias-mcp/releases) sayfasından `ilias-mcp-<sürüm>.mcpb` dosyasını indir.
2. Claude Desktop'ta **Settings → Desktop app → Manage Extensions → Advanced settings → Install Extension** yolunu izleyip paketi seç.
3. Bir Claude sohbetinde **Open ILIAS setup** de. Açılan yerel tarayıcı formuna giriş bilgilerini gir, sonra Claude'dan derslerini listelemesini iste.

Python'u ve bağımlılıkları Claude Desktop ilk açılışta kendisi yönetir. Hesabını
daha önce kurulum betiğiyle kaydettiysen derslerini hemen sorabilirsin. Elle
kurulumdan geçiyorsan, tek bir araç seti görmek için Claude Desktop'taki eski
ILIAS girdisini devre dışı bırak.
[Claude Desktop eklenti talimatları](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)

Linux'ta aynı kullanıcı oturumunda kilidi açık bir Secret Service anahtarlığı
olmalı. Daha önce kullandığın hesabı ya da şifreyi değiştirdikten sonra Claude
Desktop'u yeniden başlat.

## ChatGPT'ye bağlama

1. [OpenAI Platform](https://platform.openai.com/settings/organization/tunnels) üzerinde bir tünel oluştur ya da mevcut olanı bul, ChatGPT çalışma alanınla ilişkilendir ve **Tunnels Read + Use** yetkili bir çalışma zamanı (runtime) API anahtarı oluştur. Sistemine uygun [resmî tunnel-client](https://github.com/openai/tunnel-client/releases/latest) dosyasını indirip arşivden çıkar.
2. Çıkardığın ILIAS kaynak arşivinin ya da deponun klasöründe, sistemine uygun komutu çalıştır. `tunnel-client` `PATH` içindeyse çalıştırılabilir dosya yolunu yazmana gerek yok.

   **macOS ve Linux**

   ```bash
   bash setup.sh --chatgpt --tunnel-client /path/to/tunnel-client
   ```

   **Windows**

   ```powershell
   powershell -ExecutionPolicy Bypass -File setup.ps1 -ChatGPT -TunnelClient "C:\path\to\tunnel-client.exe"
   ```

3. İstendiğinde tünel kimliğini ve runtime anahtarını gir. ILIAS hesabının kurulması gerekiyorsa tarayıcı formu açılır. Terminali açık bırak.
4. [ChatGPT Plugins](https://chatgpt.com/plugins) sayfasında **Add custom MCP server → Tunnel**'ı seç ve tünel kimliğini seç. MCP sunucusu için **No authentication**'ı seç ve onu ILIAS hesabın için kişisel bir eklenti olarak kur. Bir sohbette `@` ile seç ve derslerini sor.

Wheel paketini kurduysan doğrudan `ilias-mcp-chatgpt` komutunu kullan. Başlatıcı
tanımlıysa `CONTROL_PLANE_TUNNEL_ID` ve `CONTROL_PLANE_API_KEY` değişkenlerini de
okur. Erişim, OpenAI hesabının ve çalışma alanının izinlerine bağlıdır.
[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) · [Add a custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server)

## Kaynaktan kurulum

**ILIAS giriş bilgilerine** ve **Python 3.10+** ya da [uv](https://docs.astral.sh/uv/getting-started/installation/) aracına ihtiyacın var.
Kaynak arşivini [GitHub Releases](https://github.com/keremilgaz/ilias-mcp/releases) sayfasından indirip çıkar
ya da bu depoyu Git ile klonla.

```bash
git clone https://github.com/keremilgaz/ilias-mcp.git
cd ilias-mcp
```

Çıkardığın ya da klonladığın klasörde, sistemine uygun komutu çalıştır.

**macOS ve Linux**

```bash
bash setup.sh
```

Debian ve Ubuntu'da Python kurulumunda eksikse `python3-venv` paketini kur.
Linux'ta ayrıca aynı kullanıcı oturumunda kilidi açık bir Secret Service
anahtarlığı (örneğin GNOME Keyring) gerekir. Windows'taki Claude için Windows
kurulum betiğini PowerShell'den çalıştır; böylece MCP sunucusu Windows Kimlik
Bilgileri Yöneticisi'ni (Credential Manager) kullanır.

**Windows**

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

Kurulum betiği yerel bir tarayıcı sayfası açar. ILIAS kullanıcı adını ve
şifreni girip **Save account**'a bas. Kurulum girişi ILIAS'ta doğrular, şifreyi
sistemin kimlik bilgisi deposuna kaydeder ve sunucuyu Claude Desktop'a ekler.
Tarayıcı açılmazsa adresi terminalden kopyala. Şifre zaten kayıtlıysa şifre
alanını boş bırak. Şifren değiştiğinde aynı kurulum komutunu yeniden çalıştır.

Claude Desktop'u tamamen kapatıp yeniden aç. Windows'ta sistem tepsisinden
çık. Ardından Claude'dan derslerini listelemesini iste.

> ILIAS'taki derslerimi listele.

Claude Desktop [macOS, Windows ve Linux (beta)](https://support.claude.com/en/articles/10065433-install-claude-desktop) için mevcut.
Giriş bilgilerini tarayıcı yerine terminalde girmek için `--terminal`
(PowerShell: `-Terminal`) kullan. ILIAS geçici olarak erişilemiyorsa
`--skip-check` (PowerShell: `-SkipCheck`) kullan.

### Diğer MCP istemcileri

Claude ayarlarını değiştirmeden hesabı kaydetmek ve yerel MCP komutunu
yazdırmak için `--no-claude` (PowerShell: `-NoClaude`) ekle. Kurulu bir wheel
paketinde aynı kurulum `ilias-mcp-config setup` olarak bulunur.

Uyumlu bir yerel MCP istemcisinde, yazdırılan komutu stdio sunucusu olarak
ayarla.

## Nasıl çalışır?

Program senin bilgisayarında çalışır ve asistanın istediğinde ILIAS
sayfalarını ya da dosyalarını alır. Önceki kontrolleri yerel olarak kaydeder;
böylece sonraki taramalar değişiklikleri raporlayabilir. Kontroller yalnızca
istek üzerine çalışır; arka planda otomatik bildirim yoktur.

**MCP**, [Model Context Protocol](https://modelcontextprotocol.io)'ün
kısaltmasıdır. Uyumlu yapay zekâ uygulamalarının bunun gibi araçları
kullanmasını sağlar. Diğer MCP istemcileri için elle yapılandırma, İngilizce
README'nin teknik bölümünde anlatılıyor.

## Hesabın ve ders verilerin

- Şifren **macOS Anahtar Zinciri**'nde, **Windows Kimlik Bilgileri
  Yöneticisi**'nde ya da bir **Linux Secret Service** anahtarlığında saklanır.
  Yerel kurulum profili yalnızca kullanıcı adını ve varsa özel indirme
  klasörünü tutar.
- Kaydedilen kontroller ve dosyalardan çıkarılan metinler bilgisayarında
  önbelleğe alınır.
- Alınan içerik **yapay zekâ uygulamanla** paylaşılır ve onun bulut model
  sağlayıcısına ulaşabilir. Yerel kurulum, yapay zekâ işlemesini yerel yapmaz.

## Mevcut kapsam

Konstanz'ın ILIAS 10 sürümü için erken bir sürüm; Almanca ve İngilizce arayüzü
destekler. Başka kurulumlar uyarlama gerektirebilir; Shibboleth/SSO girişi
desteklenmez. PDF, PowerPoint, Word, metin dosyaları ve ZIP arşivlerinden metin
okur. Taranmış görüntüler OCR gerektirir; OCR dahil değildir. Forum erişimi
başlık listeleriyle sınırlıdır.

## Teknik ayrıntılar

Teknik başvuru bölümleri İngilizce README'de güncel tutuluyor:

- [Yapılandırma ve elle kurulum, ortam değişkenleri](README.md#technical-reference)
- [Araçların listesi, okuma kayıtları, değişiklik takibi ve önbellek](README.md#technical-reference)
- [İstek politikası (salt okuma kuralları), kod yapısı ve geliştirme](README.md#technical-reference)
- [Sürümler ve yayınlar](README.md#versions-and-releases)

## Geri bildirim ve katkı

Denediysen kurulum, eksik bilgiler ya da işe yarayan bir çalışma akışı
hakkındaki geri bildirimlerin memnuniyetle karşılanır. Ne beklediğini ve ne
olduğunu yazarak bir [issue](https://github.com/keremilgaz/ilias-mcp/issues)
aç. Paylaştığın her şeyden hesap bilgilerini ve kişisel ders içeriğini çıkar.

Aracı kendi hesabınla kullan, taramaları kendi derslerinle sınırlı tut ve
üniversitenin otomatik erişim ile ders materyallerine ilişkin kurallarına uy.

## Teşekkür ve lisans

Seçici (selector) bilgileri [PFERD](https://github.com/Garmelon/PFERD) ve
[ilias-mcp (Stuttgart)](https://github.com/DenizAltunkapan/ilias-mcp)
projelerinden gelir.

[MIT](LICENSE) lisansı ile lisanslanmıştır.
