import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import dgl
import modules.attn_modules as smp_modules
from dgl.nn.pytorch.glob import AvgPooling, MaxPooling, SumPooling

embedding_mlp = {
    'layer': 1,    # number of layers.
    'in_LN': False,
    'hidden': {},
    'final': {
            'init': 'lecun',
            'bias': True,
            'act': None,
            'drop': 0.0,
        },
}


query_mlp = {
    'layer': 2,    # number of layers.
    'in_LN': False,
    'hidden': {
            'dim': 128,    # hidden dimension size
            'init': 'relu',  # initialization methods. ['kaiming', 'xavier', 'none']
            'act': nn.ReLU(),
            'bias': True,
            'norm': 'LN',
            'drop': 0.0,
        },
    'final': {
            'init': 'lecun',
            'bias': True,
            'act': None,
            'drop': 0.0,
        },
}


key_mlp = {
    'layer': 2,    # number of layers.
    'in_LN': False,
    'hidden': {
            'dim': 128,    # hidden dimension size
            'init': 'relu',  # initialization methods. ['kaiming', 'xavier', 'none']
            'act': nn.ReLU(),
            'bias': True,
            'norm': 'LN',
            'drop': 0.0,
        },
    'final': {
            'init': 'lecun',
            'bias': True,
            'act': None,
            'drop': 0.0, 
    },
}


value_mlp = {
    'layer': 2,    # number of layers.
    'in_LN': False,
    'hidden': {
            'dim': 128,    # hidden dimension size
            'init': 'relu',  # initialization methods. ['kaiming', 'xavier', 'none']
            'act': nn.ReLU(),
            'bias': True,
            'norm': 'LN',
            'drop': 0.0, 
        },
    'final': {
            'init': 'lecun',
            'bias': True,
            'act': None,
            'drop': 0.0,
        },
}


skip_mlp = {
    'layer': 2,    # number of layers.
    'in_LN': False,
    'hidden': {
            'dim': 128,    # hidden dimension size
            'init': 'relu',  # initialization methods. ['kaiming', 'xavier', 'none']
            'act': nn.ReLU(),
            'bias': True,
            'norm': 'LN',
            'drop': 0.0,
        },
    'final': {
            'init': 'lecun',
            'bias': True,
            'act': None,
            'drop': 0.0,
        },
}


out_node_graph_mlp = {
    'layer': 2,    # number of layers.
    'in_LN': False,
    'hidden': {
            'dim': 128,    # hidden dimension size
            'init': 'relu',  # initialization methods. ['kaiming', 'xavier', 'none']
            'act': nn.ReLU(),
            'bias': True,
            'norm': 'LN',
            'drop': 0.0,
        },
    'final': {
            'init': 'lecun',
            'bias': True,
            'act': None,
            'drop': 0.0,
        },
}


class NBodyModel(nn.Module):
    """Model for the NBoday simulation experiment."""
    def __init__(self, num_layers: int=3, num_hidden_channels: int=3):
        """
        :param num_layers: number of layers.
        :param num_hidden_channels: number of hidden channels.
        """
        super(NBodyModel, self).__init__()
        self.num_layers = num_layers
        self.hidden_channels = num_hidden_channels
        self.input_channels = {'vec': 1, 'scalar': 0}
        self.hidden_channels = {'vec': self.hidden_channels, 'scalar': self.hidden_channels}
        self.output_channels = {'vec': 2, 'scalar': 0}
        self.edge_dim = 1
        self.skip_type = 'cat'
        self.input_LN = False
        self.recurrent = True
        self._build_network()
        
    def _build_network(self):
        self.GBlock = nn.ModuleList()
        m_in = self.input_channels
        m_hidden = self.hidden_channels
        m_out = self.output_channels
        
        recurrent_flag = False
        inputLN_flag = False
        
        for _ in range(self.num_layers):
            self.GBlock.append(
                smp_modules.SO3EquivariantAttenRes(m_in=m_in, m_qk=m_hidden, m_v=m_hidden, m_out=m_hidden,
                                                   edge_dim=self.edge_dim, heads=1, recurrent=recurrent_flag, 
                                                   recur_drop=0.0, skip_type=self.skip_type, input_LN = inputLN_flag, 
                                                   q_archi=query_mlp, k_archi=key_mlp, v_archi=value_mlp,
                                                   out_archi=skip_mlp,))
            self.GBlock.append(smp_modules.NormBias(m_in=m_hidden, shifted='LN', init='rand'))
            m_in = m_hidden
            inputLN_flag = self.input_LN
            recurrent_flag = self.recurrent
            
        self.GBlock.append(
            smp_modules.SO3EquivariantAttenRes(m_in=m_in, m_qk=m_out, m_v=m_out, m_out=m_out,
                                               edge_dim=self.edge_dim, heads=1, recurrent=False, 
                                               recur_drop=0.0, skip_type=self.skip_type, input_LN = inputLN_flag, 
                                               q_archi=query_mlp, k_archi=key_mlp, v_archi=value_mlp,
                                               out_archi=skip_mlp,))
        
    def forward(self, G):
        """
        :param G: input graph.
        """
        features = {}
        features['vec'] = G.ndata['v']
        G.ndata['x'] = G.ndata['x'][:, 0, :]
        for layer in self.GBlock:
            features = layer(features, G=G)
        return features['vec']
    
    
class QM9Model(nn.Module):
    """Model for the QM9 experiment."""

    def __init__(self, num_layers: int,  pooling: str = 'max', heads: int = 1, div: int = 1,
                 hidden_dim:int = 128):
        """
        :param num_layers: number of layers
        :param hidden_channgels: number of hidden channels for vectors and scalars
        :param div: size of query, key, and value.
        :param heads: attention heads
        :param pooling: pooling layer
        """
        super(QM9Model, self).__init__()
        assert pooling in ['max', 'avg', 'sum'], 'Unresolved pooling type ' + pooling
        self.num_layers = num_layers
        self.my_hidden_dim = hidden_dim
        self.input_channels = {'vec': 0, 'scalar': 6}
        self.hidden_channels = {'vec': 0, 'scalar': self.my_hidden_dim}
        self.qk_channels = {'vec': 0, 'scalar': int(self.my_hidden_dim // div)}
        self.v_channels = {'vec': 0, 'scalar': int(self.my_hidden_dim // div)}
        self.output_channels = {'vec': 0, 'scalar': self.my_hidden_dim}
        self.edge_dim = 5
        self.heads = heads
        self.pooling = pooling
        self.recurrent = True
        self.skip_type = 'gate'
        self.input_LN = False

        self._build_net()

    def __repr__(self):
        return f"SimpleSO3Transformer(num_layers={self.num_layers}, hidden_channels={self.hidden_channels}, " \
               f"attention_channels={self.attention_channels}, heads={self.heads}, pooling={self.pooling}" \
               f"net_hidden_dim={self.net_hidden_dim})"

    def _build_net(self):
        m_in = self.input_channels
        m_out = self.output_channels
        m_hidden = self.hidden_channels
        m_qk = self.qk_channels
        m_v = self.v_channels

        self.embedding = smp_modules.SO3EquivariantVector(m_in_vec=m_in['vec'], m_out_vec=m_hidden['vec'],
                                                          m_in_s=m_in['scalar'], m_out_s=m_hidden['scalar'],
                                                          net_archi=embedding_mlp)
        self.edge_embedding = smp_modules.build_MLP_network(in_dim=5, out_dim=8, archi=embedding_mlp)

        self.GBlock = nn.ModuleList()
        self.GBlock.append(smp_modules.SO3LayerNorm(m_hidden))
        for _ in range(self.num_layers):
            self.GBlock.append(smp_modules.SO3EquivariantAttenRes(m_in=m_hidden, m_qk=m_qk, m_v=m_v, m_out=m_hidden,
                                                                  edge_dim=self.edge_dim, heads=self.heads,
                                                                  recurrent=self.recurrent, skip_type=self.skip_type,
                                                                  input_LN = self.input_LN, q_archi=query_mlp,
                                                                  k_archi=key_mlp, v_archi=value_mlp,
                                                                  out_archi=skip_mlp,))
            self.GBlock.append(smp_modules.NormBias(m_in=m_hidden, shifted='BN', init='zero'))
        
        self.node_mapping = smp_modules.SO3EquivariantVector(m_in_vec=m_hidden['vec'], m_out_vec=m_out['vec'],
                                                             m_in_s=m_hidden['scalar'], m_out_s=m_out['scalar'],
                                                             input_LN=self.input_LN, net_archi=out_node_graph_mlp)

        if self.pooling == 'max':
            self.pooling_layer = MaxPooling()
        elif self.pooling == 'avg':
            self.pooling_layer = AvgPooling()
        elif self.pooling == 'sum':
            self.pooling_layer = SumPooling()
        
        self.res_drop = nn.Dropout(p=0.10)
        
        self.graph_mapping = smp_modules.build_MLP_network(in_dim=m_out['scalar'], out_dim=1,
                                                           archi=out_node_graph_mlp)

    def forward(self, G):
        """
        :param G: input graph.
        """
        features = dict()
        
        # extract input features
        features['scalar'] = G.ndata['f']
        features['scalar'][:, 5, :] = features['scalar'][:, 5, :] / 9.
        
        features = self.embedding(features)

        for layer in self.GBlock:
            features = layer(features, G=G)
        
        # Post-processing and pooling
        features1 = self.node_mapping(features)['scalar']
        features = features1 + self.res_drop(features['scalar'])  # Sum
        features = self.pooling_layer(G, features[..., 0])
        
        return self.graph_mapping(features)