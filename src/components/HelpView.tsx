import React from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { Book, Map as MapIcon, Clock, MessageSquare, Dices, ScrollText, Network, HelpCircle, Eye, EyeOff } from 'lucide-react';

export const HelpView = () => {
  const { t, lang } = useLanguage();

  const sections = [
    { icon: MessageSquare, title: t.nav_chat, desc: lang === 'ru' ? 'Общение с ИИ, который знает весь контекст вашего мира. Идеально для генерации идей, диалогов или описаний.' : 'Chat with an AI that knows your entire world context. Perfect for brainstorming, dialogues, or descriptions.' },
    { icon: Book, title: t.nav_wiki, desc: lang === 'ru' ? 'База знаний вашего мира. Создавайте NPC, локации, фракции. Используйте [[Имя]] для связей.' : 'Your world\'s knowledge base. Create NPCs, locations, factions. Use [[Name]] for linking.' },
    { icon: Clock, title: t.nav_timeline, desc: lang === 'ru' ? 'Хронология событий. Отслеживайте историю мира по датам.' : 'Chronology of events. Track world history by dates.' },
    { icon: MapIcon, title: t.nav_map, desc: lang === 'ru' ? 'Интерактивная карта. Создавайте галактики, планеты или загружайте свои картинки-карты и ставьте на них пины.' : 'Interactive map. Create galaxies, planets, or upload custom map images and place pins.' },
    { icon: Dices, title: t.nav_tables, desc: lang === 'ru' ? 'Случайные таблицы для бросков (лут, энкаунтеры, погода).' : 'Random tables for rolls (loot, encounters, weather).' },
    { icon: ScrollText, title: t.nav_journal, desc: lang === 'ru' ? 'Журнал сессий. Записывайте логи игр и просите ИИ извлечь из них новых NPC и события.' : 'Session journal. Record game logs and ask AI to extract new NPCs and events.' },
    { icon: Book, title: t.nav_quests, desc: lang === 'ru' ? 'Канбан-доска для отслеживания квестов и сюжетных зацепок.' : 'Kanban board for tracking quests and plot hooks.' },
    { icon: Network, title: t.boards_title || 'Boards', desc: lang === 'ru' ? 'Доска детектива. Свободный холст для визуализации связей между персонажами и уликами.' : 'Detective board. Freeform canvas to visualize connections between characters and clues.' },
  ];

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto h-full overflow-y-auto">
      <div className="flex items-center mb-8">
        <HelpCircle size={32} className="text-emerald-500 mr-4" />
        <h2 className="text-3xl font-bold text-stone-100">{t.help_title}</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Markdown Cheat Sheet */}
        <div className="bg-stone-900 border border-stone-800 rounded-2xl p-6">
          <h3 className="text-xl font-bold text-emerald-400 mb-4 border-b border-stone-800 pb-2">
            {t.help_markdown}
          </h3>
          <div className="space-y-4 text-stone-300">
            <div>
              <code className="text-emerald-300 bg-stone-950 px-2 py-1 rounded">**Жирный текст**</code>
              <p className="text-sm text-stone-500 mt-1">Выделение важного текста.</p>
            </div>
            <div>
              <code className="text-emerald-300 bg-stone-950 px-2 py-1 rounded">*Курсив*</code>
              <p className="text-sm text-stone-500 mt-1">Наклонный текст.</p>
            </div>
            <div>
              <code className="text-emerald-300 bg-stone-950 px-2 py-1 rounded"># Заголовок 1</code><br/>
              <code className="text-emerald-300 bg-stone-950 px-2 py-1 rounded">## Заголовок 2</code>
              <p className="text-sm text-stone-500 mt-1">Создание структуры документа.</p>
            </div>
            <div>
              <code className="text-emerald-300 bg-stone-950 px-2 py-1 rounded">[[Имя Сущности]]</code>
              <p className="text-sm text-stone-500 mt-1">
                {lang === 'ru' ? 'Создает кликабельную ссылку на карточку в Вики. Пример: [[Гэндальф]]' : 'Creates a clickable link to a Wiki card. Example: [[Gandalf]]'}
              </p>
            </div>
            <div>
              <code className="text-emerald-300 bg-stone-950 px-2 py-1 rounded">1d20+5</code> или <code className="text-emerald-300 bg-stone-950 px-2 py-1 rounded">3d6</code>
              <p className="text-sm text-stone-500 mt-1">
                {lang === 'ru' ? 'Автоматически превращается в кнопку броска кубиков.' : 'Automatically turns into a dice roll button.'}
              </p>
            </div>
            <div>
              <code className="text-emerald-300 bg-stone-950 px-2 py-1 rounded">||Секретный текст||</code>
              <p className="text-sm text-stone-500 mt-1">
                {lang === 'ru' ? 'Спойлер. Текст скрыт до тех пор, пока на него не нажмут.' : 'Spoiler. Text is hidden until clicked.'}
              </p>
            </div>
            <div>
              <code className="text-emerald-300 bg-stone-950 px-2 py-1 rounded">- Элемент списка</code>
              <p className="text-sm text-stone-500 mt-1">Маркированный список.</p>
            </div>
          </div>
        </div>

        {/* App Sections */}
        <div className="bg-stone-900 border border-stone-800 rounded-2xl p-6">
          <h3 className="text-xl font-bold text-emerald-400 mb-4 border-b border-stone-800 pb-2">
            {t.help_sections}
          </h3>
          <div className="space-y-4">
            {sections.map((sec, i) => {
              const Icon = sec.icon;
              return (
                <div key={i} className="flex items-start">
                  <div className="bg-stone-950 p-2 rounded-lg mr-3 shrink-0 border border-stone-800">
                    <Icon size={18} className="text-emerald-500" />
                  </div>
                  <div>
                    <h4 className="font-bold text-stone-200">{sec.title}</h4>
                    <p className="text-sm text-stone-500 leading-relaxed">{sec.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        {/* Player Mode */}
        <div className="bg-stone-900 border border-stone-800 rounded-2xl p-6 md:col-span-2">
          <h3 className="text-xl font-bold text-emerald-400 mb-4 border-b border-stone-800 pb-2">
            {(t as any).help_player_mode || (lang === 'ru' ? 'Режим Игрока и Скрытые элементы' : 'Player Mode & Secret Elements')}
          </h3>
          <div className="space-y-4">
            <div className="flex items-start">
              <div className="bg-amber-500/10 p-2 rounded-lg mr-3 shrink-0 border border-amber-500/30 text-amber-500">
                <EyeOff size={18} />
              </div>
              <div>
                <h4 className="font-bold text-stone-200">{lang === 'ru' ? 'Секретность (Метка GM)' : 'Secret Tag (GM Marker)'}</h4>
                <p className="text-sm text-stone-500 leading-relaxed mt-1">
                  {lang === 'ru' 
                    ? 'Вы можете делать сущности в Вики, квесты на доске, логи в журнале и пины на карте Скрытыми. Ищите переключатель «Секретно». Иконка перечеркнутого глаза покажет, что элемент виден только вам.'
                    : 'You can mark Wiki entities, Quests, Journal logs, and Map pins as Secret. Look for the "Secret" toggle. The crossed-eye icon indicates the element is visible only to you.'}
                </p>
              </div>
            </div>
            
            <div className="flex items-start">
              <div className="bg-stone-800 p-2 rounded-lg mr-3 shrink-0 border border-stone-700 text-stone-400">
                <Eye size={18} />
              </div>
              <div>
                <h4 className="font-bold text-stone-200">{lang === 'ru' ? 'Режим Игрока' : 'Player Mode'}</h4>
                <p className="text-sm text-stone-500 leading-relaxed mt-1">
                  {lang === 'ru' 
                    ? 'Внизу бокового меню есть переключатель режимов. Активировав «Режим Игрока», вы можете безопасно показывать экран с приложением или передавать устройство игрокам. Все секретные элементы будут полностью скрыты, а инструменты редактирования отключены.'
                    : 'There is a mode toggle at the bottom of the sidebar. By activating "Player Mode", you can safely screen-share the app or hand the device to players. All secret elements will be completely hidden, and editing tools disabled.'}
                </p>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
