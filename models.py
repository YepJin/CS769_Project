import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
from transformers import BertConfig, BertModel, BertTokenizer
from transformers import RobertaConfig, RobertaModel, RobertaTokenizer
from transformers import AlbertConfig, AlbertModel, AlbertTokenizer
from transformers import DebertaConfig, DebertaModel, DebertaTokenizer


class EncoderImageCNN(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        pool_size = cfg['image-model']['grid']

        if cfg['image-model']['name'] == 'resnet50':
            cnn = models.resnet50(pretrained=True)
        elif cfg['image-model']['name'] == 'resnet101':
            cnn = models.resnet101(pretrained=True)

        self.spatial_feats_dim = cnn.fc.in_features
        modules = list(cnn.children())[:-2]
        self.cnn = torch.nn.Sequential(*modules)
        self.avgpool = nn.AdaptiveAvgPool2d(pool_size)

    def forward(self, image):
        spatial_features = self.cnn(image)
        spatial_features = self.avgpool(spatial_features)
        return spatial_features


class EncoderTextBERT(nn.Module):
    def __init__(self, config):
        super().__init__()
        bert_config = BertConfig.from_pretrained(config['text-model']['pretrain'],
                                                 output_hidden_states=True,
                                                 num_hidden_layers=config['text-model']['extraction-hidden-layer'])
        bert_model = BertModel.from_pretrained(config['text-model']['pretrain'], config=bert_config)

        self.tokenizer = BertTokenizer.from_pretrained(config['text-model']['pretrain'])
        self.bert_model = bert_model

    def forward(self, x, lengths):
        '''
        x: tensor of indexes (LongTensor) obtained with tokenizer.encode() of size B x ?
        lengths: tensor of lengths (LongTensor) of size B
        '''
        max_len = max(lengths)
        attention_mask = torch.ones(x.shape[0], max_len)
        for e, l in zip(attention_mask, lengths):
            e[l:] = 0
        attention_mask = attention_mask.to(x.device)

        outputs = self.bert_model(x, attention_mask=attention_mask)
        outputs = outputs[2][-1]

        return outputs


class EncoderTextROBERTA(nn.Module):
    def __init__(self, config):
        super().__init__()
        roberta_config = RobertaConfig.from_pretrained(config['text-model']['pretrain'],
                                                 output_hidden_states=True,
                                                 num_hidden_layers=config['text-model']['extraction-hidden-layer'])
        roberta_model = RobertaModel.from_pretrained(config['text-model']['pretrain'], config=roberta_config)

        self.tokenizer = RobertaTokenizer.from_pretrained(config['text-model']['pretrain'])
        self.roberta_model = roberta_model

    def forward(self, x, lengths):
        '''
        x: tensor of indexes (LongTensor) obtained with tokenizer.encode() of size B x ?
        lengths: tensor of lengths (LongTensor) of size B
        '''
        max_len = max(lengths)
        attention_mask = torch.ones(x.shape[0], max_len)
        for e, l in zip(attention_mask, lengths):
            e[l:] = 0
        attention_mask = attention_mask.to(x.device)

        outputs = self.roberta_model(x, attention_mask=attention_mask)
        outputs = outputs[2][-1]

        return outputs


class EncoderTextALBERT(nn.Module):
    def __init__(self, config):
        super().__init__()
        albert_config = AlbertConfig.from_pretrained(config['text-model']['pretrain'],
                                                 output_hidden_states=True,
                                                 num_hidden_layers=config['text-model']['extraction-hidden-layer'])
        albert_model = AlbertModel.from_pretrained(config['text-model']['pretrain'], config=albert_config)

        self.tokenizer = AlbertTokenizer.from_pretrained(config['text-model']['pretrain'])
        self.albert_model = albert_model

    def forward(self, x, lengths):
        '''
        x: tensor of indexes (LongTensor) obtained with tokenizer.encode() of size B x ?
        lengths: tensor of lengths (LongTensor) of size B
        '''
        max_len = max(lengths)
        attention_mask = torch.ones(x.shape[0], max_len)
        for e, l in zip(attention_mask, lengths):
            e[l:] = 0
        attention_mask = attention_mask.to(x.device)

        outputs = self.albert_model(x, attention_mask=attention_mask)
        outputs = outputs[2][-1]

        return outputs



class EncoderTextDEBERTA(nn.Module):
    def __init__(self, config):
        super().__init__()
        deberta_config = DebertaConfig.from_pretrained(config['text-model']['pretrain'],
                                                 output_hidden_states=True,
                                                 num_hidden_layers=config['text-model']['extraction-hidden-layer'])
        deberta_model = DebertaModel.from_pretrained(config['text-model']['pretrain'], config=deberta_config)

        self.tokenizer = DebertaTokenizer.from_pretrained(config['text-model']['pretrain'])
        self.deberta_model = deberta_model

    def forward(self, x, lengths):
        '''
        x: tensor of indexes (LongTensor) obtained with tokenizer.encode() of size B x ?
        lengths: tensor of lengths (LongTensor) of size B
        '''
        max_len = max(lengths)
        attention_mask = torch.ones(x.shape[0], max_len)
        for e, l in zip(attention_mask, lengths):
            e[l:] = 0
        attention_mask = attention_mask.to(x.device)

        outputs = self.deberta_model(x, attention_mask=attention_mask)
        outputs = outputs[1][-1]

        return outputs


class PositionalEncodingImageGrid(nn.Module):
    def __init__(self, d_model, n_regions=(4, 4)):
        super().__init__()
        assert n_regions[0] == n_regions[1]
        self.map = nn.Linear(2, d_model)
        self.n_regions = n_regions
        self.coord_tensor = self.build_coord_tensor(n_regions[0])

    @staticmethod
    def build_coord_tensor(d):
        coords = torch.linspace(-1., 1., d)
        x = coords.unsqueeze(0).repeat(d, 1)
        y = coords.unsqueeze(1).repeat(1, d)
        ct = torch.stack((x, y), dim=2)
        if torch.cuda.is_available():
            ct = ct.cuda()
        return ct

    def forward(self, x, start_token=False):   # x is seq_len x B x dim
        assert not (start_token and self.n_regions[0] == math.sqrt(x.shape[0]))
        bs = x.shape[1]
        ct = self.coord_tensor.view(self.n_regions[0]**2, -1)   # 16 x 2

        ct = self.map(ct).unsqueeze(1)   # 16 x d_model
        if start_token:
            x[1:] = x[1:] + ct.expand(-1, bs, -1)
            out_grid_point = torch.FloatTensor([-1. - 2/self.n_regions[0], -1.]).unsqueeze(0)
            if torch.cuda.is_available():
                out_grid_point = out_grid_point.cuda()
            x[0:1] = x[0:1] + self.map(out_grid_point)
        else:
            x = x + ct.expand(-1, bs, -1)
        return x


class MyWeighted(nn.Module):
    def __init__(self, num_labels):
        super(MyWeighted, self).__init__()
        self.params=nn.Parameter(torch.zeros(1, num_labels))

    def forward(self, x, y):
        params = torch.sigmoid(self.params)
        z = x * params + y * (1 - params)
        return z


class DualTransformer(nn.Module):
    def __init__(self, cfg, labels):
        super().__init__()
        embed_dim = cfg['model']['embed-dim']
        feedforward_dim = cfg['model']['feedforward-dim']
        num_encoder_layers = cfg['model']['num-encoder-layers']
        num_decoder_layers = cfg['model']['num-decoder-layers']
        visual_features_dim = cfg['image-model']['feat-dim']
        grid = cfg['image-model']['grid']
        self.text_conditioned_on_image_transformer = nn.Transformer(d_model=embed_dim, nhead=4,
                                                                    dim_feedforward=feedforward_dim,
                                                                    dropout=0.1, activation='relu',
                                                                    num_encoder_layers=num_encoder_layers,
                                                                    num_decoder_layers=num_decoder_layers)
        self.image_conditioned_on_text_transformer = nn.Transformer(d_model=embed_dim, nhead=4,
                                                                    dim_feedforward=feedforward_dim,
                                                                    dropout=0.1, activation='relu',
                                                                    num_encoder_layers=num_encoder_layers,
                                                                    num_decoder_layers=num_decoder_layers)

        self.map_text = nn.Linear(cfg['text-model']['word-dim'], embed_dim)
        self.map_image = nn.Linear(visual_features_dim, embed_dim) # + 2 spatial dimensions for encoding the image grid

        self.image_position_conditioner = PositionalEncodingImageGrid(visual_features_dim, grid)
        self.text_multi_label_class_head = nn.Linear(embed_dim, len(labels))
        self.image_multi_label_class_head = nn.Linear(embed_dim, len(labels))

        self.model_fusion = cfg['model']['model-fusion']
        if self.model_fusion == 'weighted':
            self.weighted = MyWeighted(len(labels))
        elif self.model_fusion == 'concat':
            self.concat_multi_label_class_head = nn.Linear(2 * embed_dim, len(labels))
        elif self.model_fusion == 'MLP':
            self.image_transform = nn.Linear(embed_dim, int(embed_dim / 2))
            self.text_transform = nn.Linear(embed_dim, int(embed_dim / 2))
            self.tanh = torch.nn.Tanh()
            self.comb_multi_label_class_head = nn.Linear(int(embed_dim / 2), len(labels))


    '''
    boxes: B x S x 4
    embeddings: B x S x dim
    len: B
    targets: ?
    delta_tau: B
    '''
    def forward(self, text, text_len, image):
        bs = text.shape[0]

        text = text.permute(1, 0, 2)    # S x B x dim
        # map text to a common representation space
        text = self.map_text(text)

        image = image.view(bs, image.shape[1], -1).permute(2, 0, 1)  # (d1xd2 x B x dim)

        # augment visual feats with positional info and then map to common representation space
        image = self.image_position_conditioner(image)
        image = self.map_image(image)

        # compute mask for the text (variable length)
        max_text_len = max(text_len)
        txt_mask = torch.ones(bs, max_text_len).bool()
        txt_mask = txt_mask.to(text.device)
        for m, tl in zip(txt_mask, text_len):
            m[:tl] = False

        # forward image transformer conditioned on the text
        image_out = self.image_conditioned_on_text_transformer(src=text, tgt=image, src_key_padding_mask=txt_mask, memory_key_padding_mask=txt_mask)
        contextualized_image_feature = image_out[0, :, :]
        image_class_logits = self.image_multi_label_class_head(contextualized_image_feature)

        # forward text transformer conditioned on the image
        text_out = self.text_conditioned_on_image_transformer(src=image, tgt=text, tgt_key_padding_mask=txt_mask)
        contextualized_text_feature = text_out[0, :, :]
        text_class_logits = self.text_multi_label_class_head(contextualized_text_feature)

        text_probs = torch.sigmoid(text_class_logits)
        image_probs = torch.sigmoid(image_class_logits)

        if self.model_fusion == 'weighted':
            comb_prob = self.weighted(text_probs, image_probs)
            return comb_prob
        elif self.model_fusion == 'concat':
            concat_feature = torch.cat((contextualized_image_feature, contextualized_text_feature), dim=-1)
            class_logits = self.concat_multi_label_class_head(concat_feature)
            concat_prob = torch.sigmoid(class_logits) 
            return concat_prob
        elif self.model_fusion == 'MLP':
            contextualized_image_feature = self.image_transform(contextualized_image_feature)
            contextualized_text_feature = self.text_transform(contextualized_text_feature)
            MLP_feature = self.tanh(contextualized_image_feature + contextualized_text_feature)
            MLP_feature = self.comb_multi_label_class_head(MLP_feature)
            MLP_prob = torch.sigmoid(MLP_feature)
            return MLP_prob
        else:
            return (text_probs + image_probs) / 2


class JointTransformerEncoder(nn.Module):
    def __init__(self, cfg, labels):
        super().__init__()
        embed_dim = cfg['model']['embed-dim']
        feedforward_dim = cfg['model']['feedforward-dim']
        num_layers = cfg['model']['num-layers']
        visual_features_dim = cfg['image-model']['feat-dim']
        grid = cfg['image-model']['grid']
        joint_te_layer = nn.TransformerEncoderLayer(d_model=embed_dim, nhead=4,
                                                         dim_feedforward=feedforward_dim,
                                                         dropout=0.1, activation='relu')
        self.joint_transformer = nn.TransformerEncoder(joint_te_layer,
                                                       num_layers=num_layers)

        self.map_text = nn.Linear(cfg['text-model']['word-dim'], embed_dim)
        self.map_image = nn.Linear(visual_features_dim, embed_dim) # + 2 spatial dimensions for encoding the image grid

        self.image_position_conditioner = PositionalEncodingImageGrid(visual_features_dim, grid)
        self.multi_label_class_head = nn.Linear(cfg['model']['embed-dim'], len(labels))

    '''
    boxes: B x S x 4
    embeddings: B x S x dim
    len: B
    targets: ?
    delta_tau: B
    '''
    def forward(self, text, text_len, image):
        bs = text.shape[0]

        text = text.permute(1, 0, 2)    # S x B x dim
        # map text to a common representation space
        text = self.map_text(text)

        if image is not None:
            image = image.view(bs, image.shape[1], -1).permute(2, 0, 1)  # (d1xd2 x B x dim)

            # augment visual feats with positional info and then map to common representation space
            image = self.image_position_conditioner(image)
            image = self.map_image(image)

            # merge image and text features
            image_len = [image.shape[0]] * bs
            embeddings = torch.cat([image, text], dim=0) # S+(d1xd2) x B x dim
        else:
            # only text
            image_len = [0] * bs
            embeddings = text

        # compute mask for the concatenated vector
        max_text_len = max(text_len)
        max_image_len = max(image_len)
        mask = torch.ones(bs, max_text_len + max_image_len).bool()
        mask = mask.to(embeddings.device)
        for m, tl, il in zip(mask, text_len, image_len):
            m[:il] = False
            m[max_image_len:max_image_len + tl] = False

        # forward temporal transformer
        out = self.joint_transformer(embeddings, src_key_padding_mask=mask)
        multimod_feature = out[0, :, :]

        # final multi-class head
        class_logits = self.multi_label_class_head(multimod_feature)
        probs = torch.sigmoid(class_logits)
        return probs


class MemeMultiLabelClassifier(nn.Module):
    def __init__(self, cfg, labels):
        super().__init__()
        self.visual_enabled = cfg['image-model']['enabled'] if 'enabled' in cfg['image-model'] else True
        if self.visual_enabled:
            self.visual_module = EncoderImageCNN(cfg)

        if cfg['text-model']['name'] == 'roberta':
            self.textual_module = EncoderTextROBERTA(cfg)
        elif cfg['text-model']['name'] == 'albert':
            self.textual_module = EncoderTextALBERT(cfg)
        elif cfg['text-model']['name'] == 'deberta':
            self.textual_module = EncoderTextDEBERTA(cfg)
        else:
            self.textual_module = EncoderTextBERT(cfg)

        if cfg['model']['name'] == 'transformer-encoder' or cfg['model']['name'] == 'transformer':
            self.joint_processing_module = JointTransformerEncoder(cfg, labels)
        elif cfg['model']['name'] == 'dual-transformer':
            self.joint_processing_module = DualTransformer(cfg, labels)

        self.finetune_visual = cfg['image-model']['fine-tune']
        self.finetune_textual = cfg['text-model']['fine-tune']

        self.loss = nn.BCELoss() # nn.MultiLabelSoftMarginLoss()
        self.labels = labels


    def id_to_classes(self, classes_ids):
        out_classes = []
        for elem in classes_ids:
            int_classes = []
            for idx, ids in enumerate(elem):
                if ids:
                    int_classes.append(self.labels[idx])
            out_classes.append(int_classes)
        return out_classes


    def forward(self, image, text, text_len, labels=None, return_probs=False, inference_threshold=0.5):
        if self.visual_enabled:
            with torch.set_grad_enabled(self.finetune_visual):
                image_feats = self.visual_module(image)
        else:
            image_feats = None
        with torch.set_grad_enabled(self.finetune_textual):
            text_feats = self.textual_module(text, text_len)
        probs = self.joint_processing_module(text_feats, text_len, image_feats)
        if self.training:
            loss = self.loss(probs, labels)
            return loss
        else:
            # probs = F.sigmoid(class_logits)
            loss = self.loss(probs, labels)
            if return_probs:
                return probs
            classes_ids = probs > inference_threshold
            classes = self.id_to_classes(classes_ids)
            return classes, loss