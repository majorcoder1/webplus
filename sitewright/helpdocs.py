"""Help articles written for WebPlus: web coding and site-building basics."""

ARTICLES = [
("How a web page is built", """
<p>Every page you see in a browser is a text file made of three layers.</p>
<ul>
<li><b>HTML</b> says what is on the page: headings, paragraphs, pictures, links.</li>
<li><b>CSS</b> says how it looks: colours, fonts, sizes and where things sit.</li>
<li><b>JavaScript</b> makes it do things: open a menu, show a picture bigger.</li>
</ul>
<p>WebPlus writes all three for you. Use <b>View &gt; Page HTML source</b> to see
exactly what it made. Nothing is hidden, so you can learn from it or copy parts of it.</p>"""),

("HTML in five minutes", """
<p>HTML is made of <b>tags</b> in angle brackets. Most come in pairs:</p>
<pre>&lt;h1&gt;Welcome&lt;/h1&gt;
&lt;p&gt;This is a paragraph with a &lt;a href="about/"&gt;link&lt;/a&gt;.&lt;/p&gt;
&lt;img src="images/photo.jpg" alt="A lighthouse at dusk"&gt;</pre>
<ul>
<li><code>h1</code> to <code>h6</code> are headings. Use one <code>h1</code> per page for the main title.</li>
<li><code>p</code> is a paragraph. <code>a</code> is a link. <code>img</code> is a picture.</li>
<li>The <code>alt</code> text describes a picture for people who cannot see it and for search engines.</li>
</ul>
<p>In WebPlus, set a text box's <b>Heading level</b> in the Objects panel to make it a real heading.</p>"""),

("CSS in five minutes", """
<p>CSS is a list of rules: pick something, then say how it should look.</p>
<pre>.button-red {
  background: #c8102e;
  color: white;
  border-radius: 6px;
}</pre>
<ul>
<li>Give an object a <b>CSS class</b> in the Objects panel, then style that class in
<b>Properties &gt; Page CSS</b>.</li>
<li>Colours can be names (<code>red</code>), hex (<code>#c8102e</code>) or <code>rgb(200,16,46)</code>.</li>
<li>Sizes are in <code>px</code> (pixels) or <code>%</code> (of the space available).</li>
</ul>"""),

("Meta tags and search engines", """
<p>Meta tags live in the page's <code>&lt;head&gt;</code>. Visitors never see them but
search engines and social sites read them.</p>
<ul>
<li><b>title</b> - the clickable headline in search results. Aim for under 60 characters
and make it different on every page.</li>
<li><b>description</b> - the sentence under the headline. About 120 to 160 characters.
Write a different one for every page; search engines show the page's own text only if
it has one. WebPlus's <b>Search engine optimisation</b> box keeps the page description
in one place so it cannot be missed.</li>
<li><b>robots</b> - <code>noindex</code> asks search engines to leave a page out.</li>
<li><b>canonical</b> - tells search engines the one true address of a page. Set the
site's web address in the SEO box and WebPlus adds it.</li>
<li><b>Open Graph</b> and <b>Twitter card</b> tags control how a link looks when shared.
Add a social image in the SEO box.</li>
</ul>
<p>The <i>keywords</i> tag is ignored by Google and Bing today. Fill it in only if you want to.</p>"""),

("Getting found: an SEO checklist", """
<ol>
<li>Give every page its own title and description (SEO box).</li>
<li>Use one heading level 1 per page, then level 2 and 3 for sections.</li>
<li>Add alt text to every picture. The Task Monitor reminds you.</li>
<li>Type your real web address into the SEO box so WebPlus writes a
<code>sitemap.xml</code> and <code>robots.txt</code>.</li>
<li>Submit the sitemap in Google Search Console and Bing Webmaster Tools. Paste each
site's verification code into the SEO box first.</li>
<li>Keep pages quick: WebPlus shrinks big pictures for you when it exports.</li>
<li>Make sure the site works on a phone. It does by default.</li>
</ol>"""),

("Contact forms that really work", """
<p>A form needs something on the web host to receive it and send the email.
WebPlus writes that for you: a small <code>send.php</code> file uploaded with the site.</p>
<ul>
<li>Your host must support PHP (almost all shared hosts do).</li>
<li>Set the address messages go to in <b>Insert &gt; Form email address</b>.</li>
<li>Required fields are checked in the visitor's browser and again on the server.</li>
<li>A hidden trap field stops most spam robots without a puzzle.</li>
<li>Prefer something else? Choose <b>Email program</b> (opens the visitor's mail app)
or <b>Other service</b> and paste the address your form service gives you.</li>
</ul>
<p>Build your own form with <b>Insert &gt; Form designer</b>: choose the fields, put them in
order, pick a look, and place it on the page.</p>"""),

("Make a podcast or RSS feed", """
<p>An RSS feed is a file that lists your newest posts so people can follow you in a
reader. Add audio files and it becomes a podcast.</p>
<ol>
<li>Open <b>Tools &gt; RSS feed / podcast</b> and tick <b>Publish a feed</b>.</li>
<li>Fill in the title, description, author and cover picture.</li>
<li>Add an item for each episode or post: title, date, and the audio file.</li>
<li>Type your site's web address in the SEO box. Podcast apps need full addresses.</li>
<li>Publish. Your feed is at <code>yoursite.com/feed.xml</code>. Add an
<b>RSS feed</b> button from the Social buttons so visitors find it.</li>
</ol>"""),

("Videos, maps and other pages", """
<ul>
<li><b>YouTube and Vimeo:</b> paste the link or the 11-character video ID. WebPlus
always uses a secure (https) embed so it is not blocked by browsers.</li>
<li><b>Autoplay</b> only works when the video starts muted; that is a browser rule.</li>
<li><b>Google Maps:</b> type an address and set the zoom.</li>
<li><b>Document frame:</b> shows another web page inside yours. Some sites refuse to be
shown in a frame; if the box stays empty, that is why.</li>
<li>Flash is gone from the web, so WebPlus does not offer it.</li>
</ul>"""),

("Show and hide: pop-up boxes", """
<p>To show a hidden box when something is clicked:</p>
<ol>
<li>Select the box (and anything on it) and tick <b>Hidden when the page opens</b>.</li>
<li>Group the pieces (Ctrl+G) so they appear together. The whole group is shown or hidden,
which avoids the common problem of half a pop-up showing.</li>
<li>Give the group's objects an <b>HTML id</b> of the same name, for example
<code>moreinfo</code>.</li>
<li>Select the button or text people will click, and in the link box choose
<b>Show / hide: moreinfo</b>.</li>
</ol>"""),

("Phones, tablets and wide screens", """
<p>WebPlus pages stretch their background across the whole browser window, while your
content sits in the middle at the design width you chose.</p>
<ul>
<li><b>Desktop</b> - the page is shown as you designed it.</li>
<li><b>Tablet</b> - the page scales down to fit.</li>
<li><b>Phone</b> - things stack in one column, in the order of their position. Wide
panels keep their background while the text inside wraps.</li>
</ul>
<p>Keep text boxes wide enough for their text, and put things that belong together
inside one panel so they stay together on a phone.</p>"""),

("Tidy web addresses", """
<p>With <b>clean addresses</b> on (the default) your About page is
<code>yoursite.com/about/</code> instead of <code>/about.html</code>. WebPlus makes this
work on any host by putting each page in its own folder, so you do not need to edit
<code>.htaccess</code> or any server settings.</p>
<p>If you change the setting after the site is live, old links will stop working. Search
engines will take time to learn the new addresses.</p>"""),

("Publishing and backups", """
<ul>
<li><b>File &gt; Publish site to the web (FTP)</b> sends the site to your own web host.
WebPlus does not host sites; you choose any host you like.</li>
<li>Your password is used for that upload only and is never saved.</li>
<li><b>Quick publish</b> sends only the files that changed since last time.</li>
<li>If a file fails to send, WebPlus tries again and checks the size on the server.</li>
<li><b>File &gt; Back up site</b> makes a zip holding your project and the finished site.
Keep one on a USB stick.</li>
</ul>"""),

("Sliders, rollovers and lightboxes", """
<p><b>Slider.</b> <b>Insert &gt; Slider</b> places a slide show and opens the Slider Studio.
Each panel has an optional picture, a heading, some text and a button. Choose how it moves
(slide, fade or zoom), whether it plays by itself and how long each panel stays. Visitors
can use the arrows, the dots, the arrow keys or swipe on a touch screen.</p>
<p><b>Rollover picture.</b> Select a picture and choose a <b>Rollover picture</b>: it appears
when the mouse is over it. On a phone the first tap shows it and the second follows the link.
You can also make a picture grow or brighten on mouse over.</p>
<p><b>Lightbox.</b> Tick <b>Show larger in a lightbox when clicked</b> on any picture. Add a
larger version and a caption if you like. Pictures on the same page become a set that visitors
can step through with arrows, the keyboard or a swipe.</p>"""),

("Compositions: reuse your work", """
<p>A composition is a group of objects you saved once and can use again on any page or in any
site.</p>
<ol>
<li>Select the objects (a card, a header, a sign-up strip).</li>
<li>Choose <b>Insert &gt; Save selection as composition</b>, or use the Compositions tab on the
left.</li>
<li>Double-click it in the tab to place a fresh copy, with its pictures, on the current page.</li>
</ol>
<p>Compositions are kept in your own folder, so they are there for every site you make.</p>"""),

("Site search", """
<p>Visitors can search the words on your pages, with no server needed.</p>
<ol>
<li>Make a page for the answers and put a <b>Search results</b> object on it
(<b>Insert &gt; Site search and members</b>).</li>
<li>Put a <b>Search box</b> on any page and, in its link box, choose the results page.</li>
<li>Publish. The words on each page are packed into the results page, so it also works
when you preview the site.</li>
</ol>
<p>Members-only pages and pages you hid from search engines are never searched.</p>"""),

("Members-only pages", """
<p>Keep some pages for people you choose. This needs a web host that runs PHP.</p>
<ol>
<li><b>Tools &gt; Members and protected pages</b>: add each person's user name and password.
Passwords are scrambled the moment you type them and are never saved in your file.</li>
<li>Open <b>Page Properties</b> for the page and tick <b>Members only</b>. To allow only some
members, type their names.</li>
<li>Optionally add a <b>Member login</b> object on an open page. Visitors who open a
protected page without signing in see a sign-in screen anyway.</li>
</ol>
<p>The page is checked on the server before it is sent, so its contents are not in the
code a visitor can see. Five wrong tries in a row lock the sign-in for a minute. Use a
secure (https) address for the site so passwords travel safely.</p>"""),

("Mailing list sign-up", """
<p>Add <b>Insert &gt; Site search and members &gt; Mailing list sign-up</b> where you want
people to leave their email address.</p>
<ul>
<li>Each address is saved on your own web host and emailed to your form email address.</li>
<li>Open <b>Tools &gt; Mailing list address</b> to get the private page where you can see
and download the list. Keep that address to yourself.</li>
<li>Repeat sign-ups are ignored and a hidden trap field keeps most robots out.</li>
<li>Only email people who asked to hear from you, and include a way to stop.</li>
</ul>"""),

("Special characters and superscripts", """
<p>Use <b>Text &gt; Insert symbol</b> for characters you cannot type: &copy; &reg; &trade;
&deg; &frac12; and superscripts &sup1; &sup2; &sup3; and the rest. They are ordinary text,
so they print and show on every device.</p>"""),

("Drawing: pen, shapes and cropping", """
<p>Use the <b>Pen</b> tool (toolbox, or <b>Insert &gt; Pen</b>): click for a corner, drag for a curve,
double-click or press Enter to finish, or click the first point to close the shape.
<b>Insert &gt; Shape</b> gives 17 ready-made shapes.</p>
<ul>
<li>Double-click a shape to edit its points. Drag a point or its pink curve handles; click the line to add a
point; right-click a point to make it smooth or a corner, or delete it. Press Esc to finish.</li>
<li>Points snap to the grid and guides like everything else. Turned and flipped shapes can be edited too.</li>
<li><b>Format &gt; Crop to shape</b> cuts a picture to a shape. To use your own outline, select the picture
and the shape you drew, then choose it. Borders and glows follow the shape.</li>
</ul>"""),

("Pictures: PhotoLab and effects", """
<p>Select a picture and use <b>Format &gt; Edit photo (PhotoLab)</b> to crop (drag on the picture), turn,
flip, and change brightness, contrast, colour, warmth, sharpness, blur and dark edges. The result is saved as a
new copy of the picture; undo puts the old one back.</p>
<ul>
<li><b>Format &gt; Filter effects</b> works on any object: blur, glow, black and white, sepia, colour shift.</li>
<li><b>Picture watermark</b> writes words such as &copy; %year% %sitename% into the published picture.</li>
<li><b>Picture transparency</b> makes one colour see-through: click it on the picture.</li>
<li>Phone photos carry a hidden turn note; WebPlus turns them upright once, when you add them.</li>
</ul>"""),

("Database Merge: one design, many records", """
<p>Show a list (products, people, photos) without drawing each one.</p>
<ol>
<li><b>Tools &gt; Database Merge &gt; Create Database</b>, or Create Photo Database from a folder of pictures.
Edit Database lets you type records or import a CSV file.</li>
<li><b>Insert Repeating Area</b>: its size is the size of one record. <b>Repeating Area Layout</b> sets how many
across, the gap, sorting and a limit.</li>
<li><b>Insert Text Field</b> and <b>Insert Picture Field</b> put a field inside it. In any text you can also type
<code>{{fieldname}}</code>.</li>
</ol>
<p>The design you draw is the first record. <b>View &gt; Show other records</b> previews the rest. When you
publish, the page repeats the design for every record and moves everything below it down.</p>"""),

("PDF, picture and widget export", """
<p><b>File &gt; Publish as PDF</b> makes one PDF page for each page of the site. Web, email and page links
click. <b>Export as picture</b> saves the page or the selected objects as a PNG or JPG. <b>Export as widget</b>
turns the selected objects into one self-contained HTML file and puts an embed code on the clipboard.</p>"""),

("Blog: posts, comments and likes", """
<p>Open <b>Tools &gt; Blog manager</b> to write. Each post has a title, date, author, category, tags, a picture,
an excerpt and the writing itself. Untick <i>Published</i> to keep a draft. Then <b>Insert &gt; Blog</b> puts the
blog on a page.</p>
<ul>
<li>Formatting: a blank line starts a paragraph; <code># Heading</code>, <code>- list</code>,
<code>&gt; quote</code>, <code>**bold**</code>, <code>*italic*</code>, <code>[words](address)</code>.</li>
<li>Readers can search, pick a category, open a post in a reading window, share it, and like it.</li>
<li>Comments are kept on your host (PHP). With <i>wait for my approval</i> on, nothing appears until you open
<code>blog-admin.php?key=YOUR KEY</code> and approve it. A trap field, a speed check, a limit of two links and
a limit per visitor keep most spam out.</li>
</ul>"""),

("Web polls", """
<p><b>Insert &gt; Web poll</b>, then type the question and the choices (one per line). Choose whether results show
after voting, always, or never. Each visitor can vote once. Votes are counted on your own web host (PHP).</p>"""),

("Selling online: PayPal, Stripe, Shopify, WooCommerce", """
<p>Start with <b>Tools &gt; Shop manager</b>: add products (or import a CSV file, or bring them in from your store),
then pick how customers pay on the <b>Payments</b> tab. Place <b>Insert &gt; Shop &gt; Product</b>,
<b>Product grid</b> and a <b>Shopping cart button</b>.</p>
<ul>
<li><b>PayPal</b>: paste your Client ID for the PayPal buttons, or just your PayPal email for a simple cart.</li>
<li><b>Stripe</b>: paste a restricted secret key. It is kept in a private folder on your host, and prices are
checked there so a buyer cannot change them. Needs PHP.</li>
<li><b>Shopify</b>: store address and Storefront token. Products come in with their numbers, and the cart sends
buyers to your Shopify checkout with their items filled in.</li>
<li><b>WooCommerce</b>: your store address. Each product gets a button that adds it to your store's cart.</li>
</ul>
<p>Shipping (a flat amount) and tax (a percentage) are added for PayPal and Stripe. Always check an order in
PayPal or Stripe before you ship it. Selling may need a business licence, tax registration and clear refund rules where you live.</p>"""),
]
