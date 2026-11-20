import test from 'node:test';
import assert from 'node:assert/strict';
import {parseSeason,parseEpisode,parseExpectedEpisodes,validSeriesPlan,seriesButtons} from '../individual-series.mjs';

test('saisons présentes dans la description des affiches',()=>{
 assert.equal(parseSeason('BLACK DOVES\nSaison 1 | VF'),1);
 assert.equal(parseSeason('S03 - Saison trois'),3);
 assert.equal(parseSeason('LUPIN SAISON 02\n8 épisodes'),2);
 assert.equal(parseSeason('LUPIN - nouvelle affiche sans numero'),null);
 assert.equal(parseSeason('Saison 99'),null);
});
test('épisodes dans légendes et noms de fichiers',()=>{
 assert.deepEqual(parseEpisode('Black Doves S01E02.mkv'),{season:1,episode:2});
 assert.deepEqual(parseEpisode('Saison 3 épisode 12 - VOSTFR'),{season:3,episode:12});
 assert.equal(parseEpisode('Episode 5 sans saison'),null);
});
test('comptage explicite des épisodes',()=>{
 assert.equal(parseExpectedEpisodes('Saison 1 : 12 épisodes'),12);
 assert.equal(parseExpectedEpisodes('8 episodes | Saison 2'),8);
 assert.equal(parseExpectedEpisodes('Une saison complète'),null);
});
test('livraison impossible si nombre non précisé ou saison incomplète',()=>{
 const seasons=[{season:1,expected_episodes:2},{season:2,expected_episodes:1}];
 const media=[
 {season:1,episode:1,source_message_id:11},
 {season:1,episode:2,source_message_id:12},
 {season:2,episode:1,source_message_id:35}
 ];
 assert.equal(validSeriesPlan(seasons,media),true);
 assert.equal(validSeriesPlan(seasons,media.slice(0,2)),false);
 assert.equal(validSeriesPlan([{season:1,expected_episodes:null}],media),false);
 assert.equal(validSeriesPlan([{season:2,expected_episodes:1}],[media[2]]),false);
 assert.equal(validSeriesPlan(seasons,[media[0],media[0],media[2]]),false);
});
test('boutons couleur, radar et secours à destination exacte',()=>{
 const mark=seriesButtons('abcdefghijklmnopqrstuvwx','https://t.me/+abcdefghijkL','https://t.me/addlist/ABCDEFGHIJK');
 assert.equal(mark.inline_keyboard.length,3);
 assert.equal(mark.inline_keyboard[0][0].url,'https://t.me/CineRadarFr_Bot?start=sr_abcdefghijklmnopqrstuvwx');
 assert.deepEqual(mark.inline_keyboard.map(r=>r[0].style),['success','danger','primary']);
 assert.throws(()=>seriesButtons('bad','https://t.me/+abcdefghijkL','https://t.me/addlist/ABCDEFGHIJK'));
 assert.throws(()=>seriesButtons('abcdefghijklmnopqrstuvwx','https://example.org/no','https://t.me/addlist/ABCDEFGHIJK'));
});
