require('dotenv').config();
console.log('TOKEN chargé :', process.env.TOKEN ? 'OUI ✅' : 'NON ❌');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMessages,
  ]
});

// ⚠️ Mets ici l'ID de ton salon autorisé
const SALON_AUTORISE = '1499697501115125861';

// Enregistre la slash command /dmall
client.once('ready', async () => {
  console.log(`✅ Connecté en tant que ${client.user.tag}`);

  const commands = [
    new SlashCommandBuilder()
      .setName('dmall')
      .setDescription('Envoie un DM à tous les membres du serveur')
      .addStringOption(option =>
        option.setName('message')
          .setDescription('Le message à envoyer — utilise {user} pour le pseudo du membre')
          .setRequired(true)
      )
  ].map(cmd => cmd.toJSON());

  const rest = new REST({ version: '10' }).setToken(process.env.TOKEN);

  try {
    await rest.put(
      Routes.applicationCommands(client.user.id),
      { body: commands }
    );
    console.log('✅ Slash command /dmall enregistrée !');
  } catch (err) {
    console.error('❌ Erreur enregistrement commande :', err);
  }
});

// Gestion de la commande /dmall
client.on('interactionCreate', async (interaction) => {
  if (!interaction.isChatInputCommand()) return;
  if (interaction.commandName !== 'dmall') return;

  // Vérification du salon
  if (interaction.channelId !== SALON_AUTORISE) {
    return interaction.reply({
      content: `❌ Cette commande est uniquement disponible dans <#${SALON_AUTORISE}> !`,
      ephemeral: true
    });
  }

  // Vérification admin
  if (!interaction.member.permissions.has('Administrator')) {
    return interaction.reply({
      content: '❌ Tu dois être administrateur pour utiliser cette commande !',
      ephemeral: true
    });
  }

  const customMessage = interaction.options.getString('message');

  await interaction.reply({
    content: '📨 Envoi des DMs en cours...',
    ephemeral: true
  });

  // Récupère tous les membres du serveur
  const members = await interaction.guild.members.fetch();

  let success = 0;
  let failed = 0;

  for (const [, member] of members) {
    if (member.user.bot) continue; // Ignore les bots

    // Personnalisation du message
    const personalizedMsg = customMessage
      .replace(/{user}/g, member.displayName)
      .replace(/{tag}/g, member.user.tag);

    try {
      await member.send(personalizedMsg);
      success++;
      // Pause pour éviter le rate limit Discord
      await new Promise(r => setTimeout(r, 1000));
    } catch (err) {
      failed++; // Membre avec DMs fermés
    }
  }

  await interaction.followUp({
    content: `✅ Terminé ! **${success}** DMs envoyés avec succès, **${failed}** échoués (DMs fermés).`,
    ephemeral: true
  });
});

client.login(process.env.TOKEN);
